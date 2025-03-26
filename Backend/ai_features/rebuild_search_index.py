# In ai_features/management/commands/rebuild_search_index.py
from django.core.management.base import BaseCommand
from products.models import Product, Vendor
from ai_features.clip_pineconesearch import CLIPPineconeSearch
import os
import traceback

class Command(BaseCommand):
    help = 'Rebuild the image search index'

    def add_arguments(self, parser):
        parser.add_argument('--vendor', type=int, help='Vendor ID to index products for')
        parser.add_argument('--clear', action='store_true', help='Clear existing index before rebuilding')

    def handle(self, *args, **options):
        try:
            # Initialize CLIP search
            clip_search = CLIPPineconeSearch()
            self.stdout.write('CLIP search initialized')
            
            # Clear index if requested
            if options['clear']:
                try:
                    clip_search.index.delete(delete_all=True)
                    self.stdout.write('Cleared existing index')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Could not clear index: {str(e)}'))
            
            # Get products to index
            if options['vendor']:
                # Get specific vendor
                try:
                    vendor = Vendor.objects.get(id=options['vendor'])
                    self.stdout.write(f'Indexing products for vendor {vendor.id}: {vendor.name}')
                    products = Product.objects.filter(vendor=vendor, product_images__isnull=False).distinct()
                except Vendor.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f'Vendor ID {options["vendor"]} not found'))
                    return
            else:
                # Index all products
                self.stdout.write('Indexing products for all vendors')
                products = Product.objects.filter(product_images__isnull=False).distinct()
            
            # Show product count
            self.stdout.write(f'Found {products.count()} products to index')
            
            # Track success
            indexed = 0
            failed = 0
            
            # Process each product
            for product in products:
                try:
                    # Debug info
                    self.stdout.write(f'Processing product {product.id}: {product.name}')
                    
                    # Check if product has images
                    images = product.product_images.all()
                    if not images.exists():
                        self.stdout.write(f'  No images found')
                        continue
                    
                    # Check if image file exists
                    img = images.first()
                    if not os.path.exists(img.image.path):
                        self.stdout.write(f'  Image file not found: {img.image.path}')
                        continue
                    
                    # Try to index
                    result = clip_search.index_product(product)
                    if result:
                        indexed += 1
                        self.stdout.write(f'  Successfully indexed')
                    else:
                        failed += 1
                        self.stdout.write(f'  Failed to index')
                        
                except Exception as e:
                    failed += 1
                    self.stdout.write(self.style.ERROR(f'  Error: {str(e)}'))
            
            # Check final count
            stats = clip_search.index.describe_index_stats()
            self.stdout.write(self.style.SUCCESS(f'\nIndexing complete: {indexed} products indexed, {failed} failed'))
            self.stdout.write(self.style.SUCCESS(f'Pinecone has {stats.total_vector_count} vectors'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            self.stdout.write(self.style.ERROR(traceback.format_exc()))