import logging
from django.db.models import Q
from products.models import Product
from .clip_pineconesearch import CLIPPineconeSearch

logger = logging.getLogger(__name__)

def index_new_products():
    """Index products that haven't been indexed yet"""
    logger.info("Starting indexing for new products")
    
    try:
        semantic_search = CLIPPineconeSearch()
        
        # Simplified approach - index all products with images
        new_products = Product.objects.filter(product_images__isnull=False).distinct()
        
        # Index new products
        total_indexed = 0
        for product in new_products:
            if semantic_search.index_product(product):
                total_indexed += 1
        
        logger.info(f"Indexed {total_indexed} new products")
        return total_indexed
    except Exception as e:
        logger.error(f"Error in index_new_products task: {str(e)}")
        return 0

def index_vendor_products(vendor_id):
    """Index all products for a specific vendor"""
    logger.info(f"Starting product indexing for vendor {vendor_id}")
    
    try:
        semantic_search = CLIPPineconeSearch()
        return semantic_search.index_vendor_products(vendor_id)
    except Exception as e:
        logger.error(f"Error in index_vendor_products task: {str(e)}")
        return 0

def index_new_products():
    """Index products that haven't been indexed yet"""
    logger.info("Starting indexing for new products")
    
    try:
        semantic_search = CLIPPineconeSearch()
        
        # Get all product IDs that are in Weaviate
        indexed_products = semantic_search.weaviate.query.get(
            "Product", ["product_id"]
        ).with_limit(10000).do()
        
        if "data" in indexed_products and "Get" in indexed_products["data"] and "Product" in indexed_products["data"]["Get"]:
            indexed_product_ids = [item.get("product_id") for item in indexed_products["data"]["Get"]["Product"]]
        else:
            indexed_product_ids = []
        
        # Get products that are not indexed yet and have images
        new_products = Product.objects.filter(
            product_images__isnull=False
        ).exclude(
            id__in=indexed_product_ids
        ).distinct()
        
        # Index new products
        total_indexed = 0
        for product in new_products:
            if semantic_search.index_product(product):
                total_indexed += 1
        
        logger.info(f"Indexed {total_indexed} new products")
        return total_indexed
    except Exception as e:
        logger.error(f"Error in index_new_products task: {str(e)}")
        return 0
    
def rebuild_search_index():
    """Task to rebuild the image search index"""
    from ai_features.clip_pineconesearch import CLIPPineconeSearch
    from products.models import Product
    
    clip_search = CLIPPineconeSearch()
    products = Product.objects.filter(product_images__isnull=False).distinct()
    
    indexed = 0
    
    for product in products:
        try:
            if clip_search.index_product(product):
                indexed += 1
        except Exception as e:
            print(f"Error indexing product {product.id}: {str(e)}")
    
    print(f"Index rebuild complete: {indexed} products indexed")
    return indexed