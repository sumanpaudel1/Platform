from PIL import Image
import numpy as np
import torch
from torchvision import models, transforms
from django.conf import settings
from pinecone import Pinecone
import os

class VectorDatabase:
    def __init__(self):
        # Initialize ResNet50 instead of ResNet18 for 2048 dimensions
        self.model = models.resnet50(weights='DEFAULT')
        self.model = torch.nn.Sequential(*(list(self.model.children())[:-1]))
        self.model.eval()
        
        # Image transformations
        self.transform = transforms.Compose([
            transforms.Resize(224),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])

        # Initialize Pinecone
        try:
            self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            self.index = self.pc.Index(
                host=settings.PINECONE_HOST
            )
            print("Successfully connected to Pinecone index")
        except Exception as e:
            print(f"Error initializing Pinecone: {str(e)}")
            self.index = None

    def extract_features(self, img):
        """Extract features from image using ResNet50"""
        try:
            # Prepare image
            img_tensor = self.transform(img).unsqueeze(0)
            
            # Extract features
            with torch.no_grad():
                features = self.model(img_tensor)
                # ResNet50 outputs 2048 dimensions
                features = features.reshape(1, 2048)
            
            return features.squeeze().numpy()
        except Exception as e:
            print(f"Feature extraction error: {str(e)}")
            return None
        

    def search_by_image(self, vendor_id, img, k=12):
        """Search for similar products using an image"""
        try:
            if not self.index:
                raise Exception("Pinecone index not initialized")
                
            # Extract features
            query_features = self.extract_features(img)
            if query_features is None:
                raise Exception("Failed to extract features from image")
            
            # Search in Pinecone
            results = self.index.query(
                vector=query_features.tolist(),
                filter={"vendor_id": str(vendor_id)},
                top_k=k,
                include_metadata=True
            )
            
            # Format results
            search_results = []
            seen_products = set()
            
            if 'matches' in results:
                for match in results['matches']:
                    try:
                        metadata = match.get('metadata', {})
                        product_id = int(metadata.get('product_id', 0))
                        if product_id and product_id not in seen_products:
                            # Cap similarity score at 100%
                            similarity_score = min(float(match.get('score', 0) * 100), 100)
                            search_results.append({
                                'product_id': product_id,
                                'similarity_score': similarity_score
                            })
                            seen_products.add(product_id)
                    except Exception as e:
                        print(f"Error processing match: {str(e)}")
                        continue
            
            return search_results
            
        except Exception as e:
            print(f"Search error: {str(e)}")
            return []
    
    def index_product_images(self, vendor_id, products):
        """Index product images in Pinecone"""
        try:
            if not self.index:
                raise Exception("Pinecone index not initialized")
                
            vectors_to_upsert = []
            
            for product in products:
                for image in product.product_images.all():
                    try:
                        img = Image.open(image.image.path).convert('RGB')
                        features = self.extract_features(img)
                        
                        if features is not None:
                            vector_id = f"v{vendor_id}_p{product.id}_i{image.id}"
                            vectors_to_upsert.append({
                                'id': vector_id,
                                'values': features.tolist(),
                                'metadata': {
                                    "vendor_id": str(vendor_id),
                                    "product_id": str(product.id),
                                    "image_id": str(image.id)
                                }
                            })
                            
                    except Exception as e:
                        print(f"Error processing image: {str(e)}")
                        continue
            
            # Upsert in batches
            if vectors_to_upsert:
                batch_size = 100
                for i in range(0, len(vectors_to_upsert), batch_size):
                    batch = vectors_to_upsert[i:i + batch_size]
                    self.index.upsert(vectors=batch)
                print(f"Indexed {len(vectors_to_upsert)} images successfully")
                    
        except Exception as e:
            print(f"Indexing error: {str(e)}")