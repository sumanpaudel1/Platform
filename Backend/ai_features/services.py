import logging
from PIL import Image
from io import BytesIO
from django.db import transaction
from django.utils import timezone
from products.models import Product
from .models import SearchQuery, SearchResult
# Change this import line
from .clip_pineconesearch import CLIPPineconeSearch
from .recommendations import ContentBasedRecommender

logger = logging.getLogger(__name__)

def process_image_search(vendor, image_data, max_results=12):
    """Process image search and save analytics data"""
    try:
        # Initialize CLIP search
        semantic_search = CLIPPineconeSearch()
        
        # Convert image data to PIL Image
        img = Image.open(BytesIO(image_data)).convert('RGB')
        
        # Perform search
        search_results = semantic_search.search(
            vendor_id=vendor.id,
            query_image=img,
            top_k=max_results
        )
        
        # Save search analytics
        with transaction.atomic():
            search_query = SearchQuery.objects.create(
                vendor=vendor,
                is_image_search=True,
                result_count=len(search_results),
                timestamp=timezone.now()
            )
            
            # Save individual results
            for position, result in enumerate(search_results):
                SearchResult.objects.create(
                    search_query=search_query,
                    product_id=result['product_id'],
                    similarity_score=result['similarity_score'],
                    position=position + 1
                )
        
        return search_results
    except Exception as e:
        logger.error(f"Error processing image search: {str(e)}")
        return []
    
    
def process_text_search(vendor, query_text, max_results=12):
    """Process text search and save analytics data"""
    try:
        # Initialize semantic search
        semantic_search = CLIPPineconeSearch()
        
        # Perform search
        search_results = semantic_search.search(
            vendor_id=vendor.id,
            query_text=query_text,
            top_k=max_results
        )
        
        # Save search analytics
        with transaction.atomic():
            search_query = SearchQuery.objects.create(
                vendor=vendor,
                query_text=query_text,
                is_image_search=False,
                result_count=len(search_results),
                timestamp=timezone.now()
            )
            
            # Save individual results
            for position, result in enumerate(search_results):
                SearchResult.objects.create(
                    search_query=search_query,
                    product_id=result['product_id'],
                    similarity_score=result['similarity_score'],
                    position=position + 1
                )
        
        return search_results
    except Exception as e:
        logger.error(f"Error processing text search: {str(e)}")
        return []

def get_similar_products_for_product(product, max_items=6, threshold=60.0):
    """Get similar products for product detail page with category prioritization"""
    try:
        # Initialize recommender
        from ai_features.recommendations import ContentBasedRecommender
        recommender = ContentBasedRecommender()
        
        # Get similar products with threshold
        similar_products = recommender.get_similar_products(
            product, 
            max_items=max_items,
            threshold=threshold
        )
        
        # Add debug logging
        print(f"Found {len(similar_products)} similar products for product {product.id} with threshold {threshold}")
        
        return similar_products
    except Exception as e:
        import traceback
        print(f"Error getting similar products: {str(e)}")
        print(traceback.format_exc())
        
        # Fallback to category-based recommendations
        fallback = Product.objects.filter(
            category=product.category, 
            vendor=product.vendor
        ).exclude(
            id=product.id
        ).order_by('-created_at')[:max_items]
        
        print(f"Falling back to {fallback.count()} category-based recommendations")
        
        return fallback


def get_recommended_products_for_homepage(vendor, max_items=8):
    """Get recommended products for homepage prioritizing personalization"""
    try:
        # Try using AI-based recommendations first
        try:
            from ai_features.recommendations import ContentBasedRecommender
            recommender = ContentBasedRecommender()
            
            # Try getting recommendations directly from vendor_id
            recommended = recommender.get_recommended_products(
                vendor_id=vendor.id,
                max_items=max_items,
                threshold=50.0
            )
            
            if recommended:
                print(f"Found {len(recommended)} AI-based recommendations")
                return recommended
                
            # If that fails, try the seed product approach
            seed_product = Product.objects.filter(vendor=vendor).order_by('-created_at').first()
            
            if seed_product:
                # Get recommendations based on this seed
                recommended = recommender.get_similar_products(
                    seed_product,
                    max_items=max_items,
                    threshold=60.0
                )
                
                if recommended:
                    print(f"Found {len(recommended)} seed-based recommendations")
                    return recommended
                    
        except Exception as e:
            print(f"Error in AI recommendations: {str(e)}")
        
        # Fallback to most recent products
        products = list(Product.objects.filter(vendor=vendor).order_by('-created_at')[:max_items])
        print(f"Using {len(products)} recent products as recommendations")
        return products
        
    except Exception as e:
        print(f"Recommendation error: {str(e)}")
        return []