from django.core.management.base import BaseCommand
from products.models import Product, Vendor
from ai_features.clip_pineconesearch import CLIPPineconeSearch
import os
from PIL import Image
import random

class Command(BaseCommand):
    help = 'Test image search by indexing products and searching'

    def handle(self, *args, **options):
        self.stdout.write('Testing image search...')
        
        try:
            # Initialize CLIP search
            clip_search = CLIPPineconeSearch()
            self.stdout.write('CLIP search initialized')
            
            # Get a vendor 
            vendor = Vendor.objects.first()
            if not vendor:
                self.stdout.write(self.style.ERROR('No vendors found'))
                return
            
            self.stdout.write(f'Using vendor {vendor.id}: {vendor.name}')
            
            # Get products with images
            products = Product.objects.filter(
                vendor=vendor, 
                product_images__isnull=False
            ).distinct()
            
            self.stdout.write(f'Found {products.count()} products with images')
            
            # Index products
            successful = 0
            for product in products:
                try:
                    # Check if product has images
                    images = product.product_images.all()
                    if not images.exists():
                        self.stdout.write(f'Product {product.id} has no images')
                        continue
                    
                    # Check if image file exists
                    img = images.first()
                    if not os.path.exists(img.image.path):
                        self.stdout.write(f'Product {product.id} image not found: {img.image.path}')
                        continue
                        
                    # Try to index
                    result = clip_search.index_product(product)
                    if result:
                        successful += 1
                        self.stdout.write(f'Indexed product {product.id}: {product.name}')
                    else:
                        self.stdout.write(f'Failed to index product {product.id}')
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error indexing product {product.id}: {str(e)}'))
            
            self.stdout.write(f'Successfully indexed {successful}/{products.count()} products')
            
            # Check Pinecone
            stats = clip_search.index.describe_index_stats()
            self.stdout.write(f'Pinecone has {stats.total_vector_count} vectors')
            
            # If products were indexed, test search
            if successful > 0:
                # Use one product's image for search
                test_product = random.choice(products)
                test_image_path = test_product.product_images.first().image.path
                
                if os.path.exists(test_image_path):
                    self.stdout.write(f'Testing search with image from product {test_product.id}')
                    
                    # Open image
                    image = Image.open(test_image_path).convert('RGB')
                    
                    # Search
                    results = clip_search.search(vendor.id, query_image=image)
                    
                    self.stdout.write(f'Search returned {len(results)} results')
                    
                    # Display results
                    for i, result in enumerate(results[:5]):  # Show top 5
                        self.stdout.write(f'Result {i+1}: Product {result.get("product_id")} - Score: {result.get("similarity_score"):.2f}%')
            
        except Exception as e:
            import traceback
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            self.stdout.write(self.style.ERROR(traceback.format_exc()))