import os
import sys
import django

# Add the parent directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Mock AI modules before Django setup to prevent them from loading
sys.modules['ai_features.clip_pineconesearch'] = type('dummy', (), {
    'CLIPPineconeSearch': type('CLIPPineconeSearch', (), {
        '__init__': lambda *args, **kwargs: None,
        'search_text': lambda *args, **kwargs: [],
        'search_image': lambda *args, **kwargs: []
    })
})
sys.modules['ai_features.views'] = type('dummy', (), {})
sys.modules['torch'] = type('dummy', (), {})
sys.modules['clip'] = type('dummy', (), {})

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Backend.settings')

# Initialize Django
django.setup()

# Now we can import Django models safely
from django.db import transaction
from products.models import ProductImage
import cloudinary
import cloudinary.uploader
from django.conf import settings

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
    api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
    api_secret=settings.CLOUDINARY_STORAGE['API_SECRET'],
    secure=True
)

def upload_product_image(image_file, vendor_id, product_id=None):
    """Upload a product image to Cloudinary"""
    try:
        # Create a folder structure based on CLOUDINARY_STORAGE prefix
        prefix = settings.CLOUDINARY_STORAGE.get('PREFIX', 'platform/products')
        folder = f"{prefix}/{vendor_id}"
        if product_id:
            folder = f"{folder}/{product_id}"
            
        # Upload to Cloudinary with automatic format and quality
        result = cloudinary.uploader.upload(
            image_file,
            folder=folder,
            resource_type="image",
            use_filename=True,
            unique_filename=True,
            transformation=[
                {"quality": "auto:good", "fetch_format": "auto"}
            ]
        )
        
        return {
            'url': result['secure_url'],
            'public_id': result['public_id']
        }
    except Exception as e:
        print(f"Cloudinary upload error: {str(e)}")
        return None

def migrate_images(batch_size=5, offset=0, limit=None):
    """Migrate product images to Cloudinary"""
    print("Starting migration of images to Cloudinary...")
    
    # Count images that need migration
    total_images = ProductImage.objects.filter(image_url__isnull=True).count()
    if limit:
        total_images = min(total_images, limit)
    
    print(f"Found {total_images} images to migrate starting at offset {offset}")
    
    migrated = 0
    failed = 0
    processed = 0
    
    while offset < total_images:
        # Get batch of images
        batch = ProductImage.objects.filter(
            image_url__isnull=True
        ).select_related('product__vendor')[offset:offset+batch_size]
        
        if not batch:
            break
        
        print(f"Processing batch of {len(batch)} images...")
        
        # Process each image in the batch
        for image in batch:
            try:
                if not image.image:
                    print(f"Skipping image {image.id} - no file")
                    failed += 1
                    continue
                
                try:
                    # Check if file exists
                    file_path = image.image.path
                    if not os.path.exists(file_path):
                        print(f"Skipping image {image.id} - file not found: {file_path}")
                        failed += 1
                        continue
                except Exception as e:
                    print(f"Skipping image {image.id} - error accessing file: {str(e)}")
                    failed += 1
                    continue
                
                print(f"Processing image {image.id} for product {image.product.id}...")
                
                # Upload to Cloudinary
                vendor_id = image.product.vendor.id
                product_id = image.product.id
                
                with open(file_path, 'rb') as f:
                    cloudinary_result = upload_product_image(f, vendor_id, product_id)
                
                if cloudinary_result:
                    # Update the database
                    with transaction.atomic():
                        image.image_url = cloudinary_result['url']
                        image.public_id = cloudinary_result['public_id']
                        image.save()
                    
                    print(f"✅ Image {image.id} migrated successfully")
                    migrated += 1
                else:
                    print(f"❌ Failed to upload image {image.id} to Cloudinary")
                    failed += 1
            
            except Exception as e:
                print(f"❌ Error processing image {image.id}: {str(e)}")
                failed += 1
            
            processed += 1
        
        # Update offset for next batch
        offset += batch_size
        
        # Print progress
        print(f"Progress: {processed}/{total_images} ({migrated} migrated, {failed} failed)")
    
    print(f"Migration completed: {migrated} images migrated, {failed} failed")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate product images to Cloudinary")
    parser.add_argument("--batch", type=int, default=5, help="Number of images to process in each batch")
    parser.add_argument("--offset", type=int, default=0, help="Starting offset")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of images to process")
    
    args = parser.parse_args()
    migrate_images(batch_size=args.batch, offset=args.offset, limit=args.limit)