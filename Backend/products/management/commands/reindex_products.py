from django.core.management.base import BaseCommand
from products.models import Product
from products.vector_database import VectorDatabase

class Command(BaseCommand):
    help = 'Reindex all products in Pinecone'

    def handle(self, *args, **kwargs):
        vector_db = VectorDatabase()
        products = Product.objects.all()
        
        self.stdout.write("Starting product reindexing...")
        for product in products:
            if product.product_images.exists():
                try:
                    vector_db.index_product_images(product.vendor.id, [product])
                    self.stdout.write(
                        self.style.SUCCESS(f"Successfully indexed product {product.id}")
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error indexing product {product.id}: {str(e)}")
                    )