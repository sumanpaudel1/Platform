# Fix imports - remove ai_features. prefix since we're already in that package
from clip_pineconesearch import CLIPPineconeSearch
from products.models import Product, Vendor

# For Django to load models, we need to set up Django environment
import os
import django

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Backend.settings')
django.setup()

def test_index():
    """Test indexing a single product"""
    try:
        # Initialize CLIP search
        clip_search = CLIPPineconeSearch()
        
        # Get a test product (ID 74 based on your debug)
        product = Product.objects.get(id=74)
        print(f"Testing with product: {product.id} - {product.name}")
        print(f"Category: {product.category.category_name}")
        
        # Try to index
        result = clip_search.index_product(product)
        print(f"Indexing result: {result}")
        
        # Check if product is in index
        stats = clip_search.index.describe_index_stats()
        print(f"Pinecone index now has {stats.total_vector_count} vectors")
        
        return "Success"
    except Exception as e:
        import traceback
        print(f"Error: {str(e)}")
        print(traceback.format_exc())
        return f"Error: {str(e)}"

# Run the test
if __name__ == "__main__":
    result = test_index()
    print(result)