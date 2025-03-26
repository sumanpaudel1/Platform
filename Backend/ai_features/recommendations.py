import logging
import numpy as np
from products.models import Product
from .clip_pineconesearch import CLIPPineconeSearch

logger = logging.getLogger(__name__)

class ContentBasedRecommender:
    """Recommends products based on content similarity"""
    
    def __init__(self):
        """Initialize the recommender system"""
        try:
            # Initialize search engine
            self.search_engine = CLIPPineconeSearch()
            logger.info("ContentBasedRecommender initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing ContentBasedRecommender: {str(e)}")
            self.search_engine = None
    
    def get_similar_products(self, product, max_items=6, threshold=60.0):
        """Get products similar to a given product with category prioritization"""
        try:
            if not self.search_engine:
                logger.error("Search engine not initialized")
                raise Exception("Search engine not initialized")
                
            # Use product name and description as query text
            query_text = f"{product.name} {product.description or ''} {product.category.category_name if product.category else ''}"
            
            # Get similar products using semantic search
            results = self.search_engine.search(
                vendor_id=product.vendor.id,
                query_text=query_text,
                top_k=20,  # Get more items than needed to allow for category filtering
                threshold=threshold
            )
            
            # Filter out the current product
            filtered_results = [result for result in results if str(result['product_id']) != str(product.id)]
            
            # Split results into same category and different category
            same_category_results = []
            different_category_results = []
            
            # Process all results
            for result in filtered_results:
                try:
                    result_product = Product.objects.get(id=result['product_id'])
                    result_product.similarity_score = result['similarity_score']
                    result_product.explanation = result.get('explanation', '')
                    
                    # Sort into appropriate list based on category
                    if (product.category and result_product.category and 
                        product.category.id == result_product.category.id):
                        same_category_results.append(result_product)
                    else:
                        different_category_results.append(result_product)
                    
                except Product.DoesNotExist:
                    continue
            
            # Sort both lists by similarity score in descending order
            same_category_results.sort(key=lambda p: getattr(p, 'similarity_score', 0), reverse=True)
            different_category_results.sort(key=lambda p: getattr(p, 'similarity_score', 0), reverse=True)
            
            # Combine the lists with same category first
            combined_results = same_category_results + different_category_results
            
            # Limit to requested number of items
            return combined_results[:max_items]
            
        except Exception as e:
            logger.error(f"Error getting similar products: {str(e)}")
            # Return empty list - fallback will be handled by the caller
            return []
            
    def get_recommended_products(self, vendor_id, max_items=8, category=None, threshold=60.0):
        """Get recommended products for homepage with category prioritization"""
        try:
            if not self.search_engine:
                logger.error("Search engine not initialized")
                raise Exception("Search engine not initialized")
                
            # Get popular products first (fallback if semantic search fails)
            popular_products = Product.objects.filter(vendor_id=vendor_id)
            
            if category:
                popular_products = popular_products.filter(category=category)
            
            # Order by most viewed or other popularity metric if available
            popular_products = popular_products.order_by('-created_at')[:max_items]
            
            # If no products found, return empty list
            if not popular_products.exists():
                return []
            
            # Select a "seed" product to find similar products
            seed_product = popular_products.first()
            
            # Return popular products if no seed product found
            if not seed_product:
                return list(popular_products)
                
            # Get similar products using semantic search
            try:
                query_text = f"{seed_product.name} {seed_product.category.category_name if seed_product.category else ''}"
                
                # Search with threshold
                results = self.search_engine.search(
                    vendor_id=vendor_id,
                    query_text=query_text,
                    top_k=max_items + 5,  # Get extra to allow for filtering
                    threshold=threshold    # Apply threshold filter
                )
                
                # Convert to product objects with similarity scores
                recommended_products = []
                for result in results:
                    try:
                        product = Product.objects.get(id=result['product_id'])
                        product.similarity_score = result['similarity_score']
                        recommended_products.append(product)
                    except Product.DoesNotExist:
                        logger.warning(f"Product {result['product_id']} not found")
                
                # If semantic search failed, use popularity-based recommendations
                if not recommended_products:
                    return list(popular_products)
                
                # Limit to requested number of items
                return recommended_products[:max_items]
            except Exception as e:
                logger.error(f"Error in semantic search: {str(e)}")
                return list(popular_products)
                
        except Exception as e:
            logger.error(f"Error getting recommended products: {str(e)}")
            # Fallback to popular products
            if 'popular_products' in locals():
                return list(popular_products)
            else:
                return []