from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from products.models import ProductImage
from products.utils import upload_product_image
import os
from django.db import transaction
import sys

class Command(BaseCommand):
    help = 'Migrate existing product images to Cloudinary'
    
    def add_arguments(self, parser):
        parser.add_argument('--batch', type=int, default=10, help='Batch size')
        parser.add_argument('--offset', type=int, default=0, help='Starting offset')
        parser.add_argument('--limit', type=int, default=None, help='Maximum images to process')

    def handle(self, *args, **options):
        # Disable the AI features import by adding to sys.modules
        # This prevents Django from importing the modules that cause memory issues
        sys.modules['ai_features.clip_pineconesearch'] = type('DummyModule', (), {})
        sys.modules['ai_features.views'] = type('DummyModule', (), {})
        
        batch_size = options['batch']
        offset = options['offset']
        limit = options['limit']
        
        # Count total images that need migration
        query = ProductImage.objects.filter(image_url__isnull=True)
        if limit:
            total = min(query.count(), limit)
        else:
            total = query.count()
            
        self.stdout.write(f"Found {total} images to migrate starting at offset {offset}")
        
        migrated = 0
        failed = 0
        
        # Process in batches
        while offset < total:
            self.stdout.write(f"Processing batch starting at {offset}")
            
            # Get batch of images
            images = query.select_related('product__vendor')[offset:offset+batch_size]
            
            for image in images:
                try:
                    if not image.image:
                        self.stdout.write(f"Skipping image {image.id} - no file")
                        failed += 1
                        continue
                    
                    try:
                        if not os.path.exists(image.image.path):
                            self.stdout.write(f"Skipping image {image.id} - file not found")
                            failed += 1
                            continue
                    except:
                        self.stdout.write(f"Skipping image {image.id} - path error")
                        failed += 1
                        continue
                    
                    # Upload to Cloudinary
                    vendor_id = image.product.vendor_id
                    product_id = image.product_id
                    
                    try:
                        file_path = image.image.path
                        self.stdout.write(f"Uploading {file_path} to Cloudinary")
                        
                        with open(file_path, 'rb') as f:
                            result = upload_product_image(
                                f, 
                                vendor_id=vendor_id,
                                product_id=product_id
                            )
                        
                        if result:
                            # Update in separate transaction
                            with transaction.atomic():
                                image.image_url = result['url']
                                image.public_id = result['public_id']
                                image.save()
                            
                            migrated += 1
                            self.stdout.write(f"Migrated image {image.id} for product {image.product_id}")
                        else:
                            self.stdout.write(f"Failed to migrate image {image.id}")
                            failed += 1
                    
                    except Exception as e:
                        self.stdout.write(f"Error uploading image {image.id}: {str(e)}")
                        failed += 1
                    
                except Exception as e:
                    self.stdout.write(f"Error processing image {image.id}: {str(e)}")
                    failed += 1
            
            # Move to next batch
            offset += batch_size
            
            # Save progress
            self.stdout.write(f"Progress: {migrated + failed}/{total} ({migrated} migrated, {failed} failed)")
        
        self.stdout.write(self.style.SUCCESS(f"Migration complete: {migrated} migrated, {failed} failed"))