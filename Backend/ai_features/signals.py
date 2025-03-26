from django.db.models.signals import post_save
from django.dispatch import receiver
from products.models import Product

# Import from clip_pineconesearch instead of semantic_search
from .clip_pineconesearch import CLIPPineconeSearch

@receiver(post_save, sender=Product)
def index_product_on_save(sender, instance, created, **kwargs):
    """Index product when it's created or updated"""
    try:
        # Skip if it doesn't have images
        if not instance.product_images.exists():
            return
            
        # Use CLIPPineconeSearch instead of SemanticSearch
        clip_search = CLIPPineconeSearch()
        clip_search.index_product(instance)
    except Exception as e:
        # Just log the error, don't break the save operation
        print(f"Error indexing product: {str(e)}")