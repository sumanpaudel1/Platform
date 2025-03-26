import torch
import clip
import numpy as np
import os
import io
import logging
from PIL import Image
from django.conf import settings
from products.models import Product
from pinecone import Pinecone
from datetime import datetime

logger = logging.getLogger(__name__)

class CLIPPineconeSearch:
    """CLIP-based semantic search using Pinecone instead of Weaviate"""
    
    
    def get_category_name(self, product):
        """Safely get category name regardless of model structure"""
        if not product.category:
            return "Uncategorized"
            
        # Your Category model uses category_name, not name!
        if hasattr(product.category, 'category_name'):
            return product.category.category_name
        
        # Fallbacks
        if hasattr(product.category, 'name'):
            return product.category.name
        elif hasattr(product.category, 'title'):
            return product.category.title
        elif hasattr(product.category, 'category'):
            return product.category.category
        
        # Last resort - string representation
        return str(product.category)
    
    def __init__(self):
        # Initialize CLIP model
        try:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model, self.preprocess = clip.load("ViT-B/32", device=self.device)
            logger.info(f"CLIP model loaded successfully. Using device: {self.device}")
            
            # Initialize Pinecone - USE INDEX_NAME NOT HOST
            self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            
            # CRITICAL: Use PINECONE_INDEX_NAME, not PINECONE_HOST
            self.index = self.pc.Index(settings.PINECONE_INDEX_NAME)
            logger.info("Successfully connected to Pinecone index")
            
        except Exception as e:
            logger.error(f"Error initializing CLIPPineconeSearch: {str(e)}")
            self.index = None
            raise
    
    def encode_image(self, image):
        """Encode image to embedding vector using CLIP"""
        try:
            image_input = self.preprocess(image).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                image_features = self.model.encode_image(image_input)
                
            # Return normalized features
            features = image_features.cpu().numpy()[0]
            features = features / np.linalg.norm(features)
            return features
        except Exception as e:
            logger.error(f"Error encoding image: {str(e)}")
            return None
    
    def encode_text(self, text):
        """Encode text to embedding vector using CLIP"""
        try:
            text_input = clip.tokenize([text]).to(self.device)
            
            with torch.no_grad():
                text_features = self.model.encode_text(text_input)
                
            # Return normalized features
            features = text_features.cpu().numpy()[0]
            features = features / np.linalg.norm(features)
            return features
        except Exception as e:
            logger.error(f"Error encoding text: {str(e)}")
            return None
    
    def index_product(self, product):
        """Index a single product in Pinecone"""
        try:
            if self.index is None:
                logger.error("Pinecone index not initialized")
                print(f"Indexing product {product.id} - Category: {product.category}")
                return False

                
            # Skip if product has no images
            if not product.product_images.exists():
                logger.warning(f"Product {product.id} has no images, skipping indexing")
                return False
            
            # Get the main image
            main_image = product.product_images.first()
            image_path = main_image.image.path
            
            # Check if image exists
            if not os.path.exists(image_path):
                logger.warning(f"Image {image_path} does not exist, skipping indexing")
                return False
            
            # Load and process the image
            image = Image.open(image_path).convert('RGB')
            
            # Get product text for text embedding
            product_text = f"{product.name} {product.description or ''} {self.get_category_name(product)}"
            
            # Generate embeddings
            image_embedding = self.encode_image(image)
            text_embedding = self.encode_text(product_text)
            
            # Combine embeddings (average)
            combined_embedding = (image_embedding + text_embedding) / 2
            combined_embedding = combined_embedding / np.linalg.norm(combined_embedding)
            
            # Create vector ID
            vector_id = f"clip_v{product.vendor.id}_p{product.id}"
            
            # Create metadata
            metadata = {
                "product_id": product.id,
                "vendor_id": product.vendor.id,
                "name": product.name,
                "description": product.description or "",
                "category": self.get_category_name(product),  # FIXED
                "price": float(product.price),
                "last_updated": datetime.now().isoformat()
            }
            
            # Upsert vector to Pinecone
            self.index.upsert(
                vectors=[
                    {
                        "id": vector_id,
                        "values": combined_embedding.tolist(),
                        "metadata": metadata
                    }
                ]
            )
            
            logger.info(f"Indexed product {product.id} in Pinecone with CLIP")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing product {product.id}: {str(e)}")
            return False
    
    def index_vendor_products(self, vendor_id):
        """Index all products for a vendor"""
        try:
            products = Product.objects.filter(vendor_id=vendor_id).prefetch_related('product_images', 'category')
            
            indexed_count = 0
            total_count = len(products)
            
            # Index in batches of 100 for better performance
            batch_size = 100
            for i in range(0, total_count, batch_size):
                batch = products[i:i+batch_size]
                vectors_to_upsert = []
                
                for product in batch:
                    try:
                        # Skip if product has no images
                        if not product.product_images.exists():
                            continue
                        
                        # Get the main image
                        main_image = product.product_images.first()
                        image_path = main_image.image.path
                        
                        # Check if image exists
                        if not os.path.exists(image_path):
                            continue
                        
                        # Load and process the image
                        image = Image.open(image_path).convert('RGB')
                        
                        # Get product text for text embedding
                        product_text = f"{product.name} {product.description or ''} {self.get_category_name(product)}"
                        
                        # Generate embeddings
                        image_embedding = self.encode_image(image)
                        text_embedding = self.encode_text(product_text)
                        
                        # Combine embeddings (average)
                        combined_embedding = (image_embedding + text_embedding) / 2
                        combined_embedding = combined_embedding / np.linalg.norm(combined_embedding)
                        
                        # Create vector ID and metadata
                        vector_id = f"clip_v{product.vendor.id}_p{product.id}"
                        metadata = {
                            "product_id": product.id,
                            "vendor_id": product.vendor.id,
                            "name": product.name,
                            "description": product.description or "",
                            "category": self.get_category_name(product),  # FIXED - Using helper method
                            "price": float(product.price),
                            "last_updated": datetime.now().isoformat()
                        }
                        
                        vectors_to_upsert.append({
                            "id": vector_id,
                            "values": combined_embedding.tolist(),
                            "metadata": metadata
                        })
                        
                        indexed_count += 1
                    except Exception as e:
                        logger.error(f"Error processing product {product.id}: {str(e)}")
                
                # Upsert batch to Pinecone
                if vectors_to_upsert:
                    self.index.upsert(vectors=vectors_to_upsert)
                
                # Log progress
                logger.info(f"Indexed {i+len(batch)}/{total_count} products for vendor {vendor_id}")
            
            logger.info(f"Completed indexing {indexed_count}/{total_count} products for vendor {vendor_id}")
            return indexed_count
        except Exception as e:
            logger.error(f"Error indexing vendor products: {str(e)}")
            return 0
    

    def search(self, vendor_id, query_image=None, query_text=None, top_k=12, threshold=60.0):
        """Search for similar products using image and/or text with threshold filtering"""
        try:
            # Add debug info
            stats = self.index.describe_index_stats()
            print(f"Pinecone index stats: {stats.total_vector_count} vectors, dimension {stats.dimension}")
            
            if self.index is None:
                logger.error("Pinecone index not initialized")
                return []
                
            # Generate query embedding
            query_embedding = None
            
            if query_image:
                image_embedding = self.encode_image(query_image)
                if image_embedding is not None:
                    query_embedding = image_embedding
            
            if query_text:
                text_embedding = self.encode_text(query_text)
                if text_embedding is not None:
                    if query_embedding is not None:
                        # Average with image embedding
                        query_embedding = (query_embedding + text_embedding) / 2
                    else:
                        query_embedding = text_embedding
            
            if query_embedding is None:
                logger.error("Failed to generate query embedding")
                return []
            
            # Normalize the query embedding
            query_embedding = query_embedding / np.linalg.norm(query_embedding)
            
            # Query Pinecone
            results = self.index.query(
                vector=query_embedding.tolist(),
                filter={"vendor_id": vendor_id},
                top_k=top_k,
                include_metadata=True
            )
            
            # Process results with threshold filtering
            processed_results = []
            
            for i, match in enumerate(results.get('matches', [])):
                try:
                    metadata = match.get('metadata', {})
                    similarity_score = match.get('score', 0) * 100  # Convert to percentage
                    
                    # Apply threshold filtering
                    if similarity_score < threshold:
                        continue
                    
                    # Format explanation
                    category = metadata.get('category', 'Unknown')
                    explanation = self._generate_explanation(
                        similarity_score/100, 
                        category, 
                        metadata.get('name', 'Unknown'),
                        query_text
                    )
                    
                    processed_results.append({
                        "product_id": metadata.get('product_id'),
                        "similarity_score": similarity_score,
                        "category": category,
                        "explanation": explanation,
                        "position": i + 1
                    })
                except Exception as e:
                    logger.error(f"Error processing search result: {str(e)}")
            
            return processed_results
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            return []
        
    
    def _generate_explanation(self, similarity_score, category, product_name, query_text=None):
        """Generate human-readable explanation for search results"""
        confidence = similarity_score * 100
        
        if confidence >= 90:
            strength = "very strong"
        elif confidence >= 75:
            strength = "strong"
        elif confidence >= 60:
            strength = "moderate"
        elif confidence >= 40:
            strength = "weak"
        else:
            strength = "very weak"
            
        explanation = f"This {category} has a {strength} match ({confidence:.1f}%) with your search."
        
        if query_text:
            explanation += f" Your search terms '{query_text}' appear related to this product."
            
        return explanation