import os
import shutil
import urllib.request
import logging
from datetime import datetime

import torch
import clip
import clip.clip as clip_mod
import numpy as np
from PIL import Image
from django.conf import settings
from pinecone import Pinecone
from products.models import Product

logger = logging.getLogger(__name__)

def _streaming_download(url, root):
    """
    Download in small chunks to avoid slurping the entire model into RAM
    for the SHA-256 check.
    """
    os.makedirs(root, exist_ok=True)
    fname = url.split("/")[-1]
    target = os.path.join(root, fname)
    if os.path.exists(target):
        return target
    with urllib.request.urlopen(url) as resp, open(target, "wb") as out:
        shutil.copyfileobj(resp, out)
    return target

# Monkey-patch CLIP’s downloader before any clip.load() calls
clip_mod._download = _streaming_download


class CLIPPineconeSearch:
    """CLIP-driven semantic search + Pinecone indexing."""

    def __init__(self):
        # Force CPU to avoid GPU OOM
        self.device = "cpu"
        self.model = None
        self.preprocess = None
        self._model_loaded = False

        # Init Pinecone index client
        try:
            self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            self.index = self.pc.Index(settings.PINECONE_INDEX_NAME)
            logger.info("Connected to Pinecone index %s", settings.PINECONE_INDEX_NAME)
        except Exception as e:
            logger.error("Error initializing Pinecone: %s", e)
            self.index = None

    def _load_model(self):
        """Lazy-load the CLIP model once on first encode_ call."""
        if self._model_loaded:
            return True

        try:
            self.model, self.preprocess = clip.load("ViT-B/32", device=self.device)
            self._model_loaded = True
            logger.info("CLIP loaded on %s", self.device)
            return True
        except Exception as e:
            logger.error("Failed loading CLIP on %s: %s", self.device, e)
            # Retry on CPU
            try:
                self.model, self.preprocess = clip.load("ViT-B/32", device="cpu")
                self.device = "cpu"
                self._model_loaded = True
                logger.warning("Fell back to CPU for CLIP model")
                return True
            except Exception as e2:
                logger.error("Failed loading CLIP on CPU: %s", e2)
                return False

    def get_category_name(self, product: Product) -> str:
        """Extract a human-friendly category name."""
        cat = product.category
        if not cat:
            return "Uncategorized"
        for attr in ("category_name", "name", "title", "category"):
            if hasattr(cat, attr):
                return getattr(cat, attr)
        return str(cat)

    def encode_image(self, image: Image.Image) -> np.ndarray | None:
        """Return a normalized CLIP image embedding or None on error."""
        if not self._load_model():
            return None
        try:
            inp = self.preprocess(image).unsqueeze(0).to(self.device)
            with torch.no_grad():
                feats = self.model.encode_image(inp)
            arr = feats.cpu().numpy()[0]
            return arr / np.linalg.norm(arr)
        except Exception as e:
            logger.error("Error encoding image: %s", e)
            return None

    def encode_text(self, text: str) -> np.ndarray | None:
        """Return a normalized CLIP text embedding or None on error."""
        if not self._load_model():
            return None
        try:
            inp = clip.tokenize([text]).to(self.device)
            with torch.no_grad():
                feats = self.model.encode_text(inp)
            arr = feats.cpu().numpy()[0]
            return arr / np.linalg.norm(arr)
        except Exception as e:
            logger.error("Error encoding text: %s", e)
            return None

    def index_product(self, product: Product) -> bool:
        """Compute embedding and upsert one product into Pinecone."""
        if not self.index:
            logger.error("Pinecone index not initialized")
            return False

        # Need at least one image
        if not product.product_images.exists():
            logger.warning("Product %s has no images", product.id)
            return False
        img_path = product.product_images.first().image.path
        if not os.path.exists(img_path):
            logger.warning("Image %s not found", img_path)
            return False

        # Prepare embeddings
        img = Image.open(img_path).convert("RGB")
        txt = f"{product.name} {product.description or ''} {self.get_category_name(product)}"
        img_emb = self.encode_image(img)
        txt_emb = self.encode_text(txt)
        if img_emb is None or txt_emb is None:
            return False

        vec = (img_emb + txt_emb)
        vec = vec / np.linalg.norm(vec)

        pid = f"clip_v{product.vendor.id}_p{product.id}"
        meta = {
            "product_id":   product.id,
            "vendor_id":    product.vendor.id,
            "name":         product.name,
            "description":  product.description or "",
            "category":     self.get_category_name(product),
            "price":        float(product.price),
            "last_updated": datetime.now().isoformat()
        }
        try:
            self.index.upsert(vectors=[{"id": pid, "values": vec.tolist(), "metadata": meta}])
            logger.info("Indexed product %s", product.id)
            return True
        except Exception as e:
            logger.error("Upsert error for %s: %s", product.id, e)
            return False

    def search(
        self,
        vendor_id: int,
        query_image: Image.Image | None = None,
        query_text: str | None = None,
        top_k: int = 12,
        threshold: float = 60.0
    ) -> list[dict]:
        """
        Run a similarity search. Returns list of hits with metadata & explanations.
        """
        if not self.index:
            logger.error("Pinecone index not ready")
            return []

        # Build a combined embedding
        emb = None
        if query_image is not None:
            emb = self.encode_image(query_image)
        if query_text:
            txt_emb = self.encode_text(query_text)
            if txt_emb is not None:
                emb = txt_emb if emb is None else (emb + txt_emb) / 2
        if emb is None:
            logger.error("No valid query embedding")
            return []

        emb = emb / np.linalg.norm(emb)
        resp = self.index.query(
            vector=emb.tolist(),
            filter={"vendor_id": vendor_id},
            top_k=top_k,
            include_metadata=True
        )

        results = []
        for idx, match in enumerate(resp.get("matches", []), start=1):
            score = match.get("score", 0) * 100
            if score < threshold:
                continue
            meta = match.get("metadata", {})
            expl = self._generate_explanation(
                score / 100,
                meta.get("category", "Unknown"),
                meta.get("name", ""),
                query_text
            )
            results.append({
                "product_id":       meta.get("product_id"),
                "similarity_score": score,
                "category":         meta.get("category", ""),
                "explanation":      expl,
                "position":         idx
            })
        return results

    def _generate_explanation(self, sim, category, name, query_text=None) -> str:
        """Turn a score into a human-friendly sentence."""
        pct = sim * 100
        if pct >= 90:
            strength = "very strong"
        elif pct >= 75:
            strength = "strong"
        elif pct >= 60:
            strength = "moderate"
        elif pct >= 40:
            strength = "weak"
        else:
            strength = "very weak"

        txt = f"This {category} ({name}) has a {strength} match ({pct:.1f}%)."
        if query_text:
            txt += f" Your keywords “{query_text}” are relevant."
        return txt

# Optional singleton for reuse
clip_search = CLIPPineconeSearch()