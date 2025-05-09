import json
import logging
from PIL import Image
from io import BytesIO
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from accounts.models import Subdomain
from products.models import Product
from .services import (
    process_image_search,
    process_text_search,
    get_similar_products_for_product
)
from .tasks import index_vendor_products
from django.db.models import Avg, Count
from products.models import Review
import os
import io
from ai_features.clip_pineconesearch import CLIPPineconeSearch
logger = logging.getLogger(__name__)


vector_db = CLIPPineconeSearch()


@require_http_methods(["POST"])
def image_search_view(request, subdomain):
    try:
        if 'image_query' not in request.FILES:
            return JsonResponse({
                'status': 'error', 
                'message': 'No image file provided'
            })
            
        subdomain = subdomain.replace('.platform', '')
        subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
        vendor = subdomain_obj.vendor
        
        # Process query image
        image_file = request.FILES['image_query']
        img = Image.open(io.BytesIO(image_file.read())).convert('RGB')
        
        # Use CLIP search
        from ai_features.clip_pineconesearch import CLIPPineconeSearch
        clip_search = CLIPPineconeSearch()
        search_results = []
        if clip_search:
            try:
                print(f"Attempting CLIP search for vendor {vendor.id}")
                search_results = clip_search.search(vendor.id, query_image=img)
                print(f"CLIP search returned {len(search_results)} results")
                
                # If no results, try indexing
                if not search_results:
                    print(f"No CLIP results, indexing products for vendor {vendor.id}")
                    indexed_count = clip_search.index_vendor_products(vendor.id)
                    print(f"Indexed {indexed_count} products with CLIP")
                    
                    # Try search again
                    search_results = clip_search.search(vendor.id, query_image=img)
                    print(f"After indexing: CLIP search returned {len(search_results)} results")
            except Exception as e:
                print(f"CLIP search error: {str(e)}")
                # Fall back to ResNet search
                if vector_db:
                    try:
                        search_results = vector_db.search_by_image(vendor.id, img)
                    except Exception as e:
                        print(f"ResNet search error: {str(e)}")
        
        if not search_results:
            return JsonResponse({
                'status': 'error',
                'message': 'No similar products found'
            })
        
        # Store results in session
        request.session['image_search_results'] = search_results
        
        return JsonResponse({
            'status': 'success',
            'redirect_url': reverse('products:search', kwargs={'subdomain': subdomain}) + '?type=image'
        })
        
    except Exception as e:
        print(f"Image search error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })
        
        

@require_http_methods(["GET"])
def similar_products_view(request, subdomain, product_id):
    """Get similar products for a specific product"""
    try:
        subdomain = subdomain.replace('.platform', '')
        subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
        vendor = subdomain_obj.vendor
        
        product = get_object_or_404(Product, id=product_id, vendor=vendor)
        
        # Get similar products
        similar_products = get_similar_products_for_product(product)
        
        # Format response
        result = {
            'status': 'success',
            'similar_products': []
        }
        
        for product in similar_products:
            # Get main image URL
            image_url = None
            if product.product_images.exists():
                image_url = product.product_images.first().image.url
                
            result['similar_products'].append({
                'id': product.id,
                'name': product.name,
                'price': float(product.price),
                'image_url': image_url,
                'url': reverse('products:product_detail', kwargs={
                    'subdomain': subdomain,
                    'slug': product.slug
                }),
                'similarity_score': getattr(product, 'similarity_score', None)
            })
        
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Similar products error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })

@require_http_methods(["GET"])
def index_products_view(request, subdomain):
    """Admin view to index all products for a vendor"""
    try:
        # Check if user is authenticated and is admin/vendor
        if not request.user.is_authenticated or not (request.user.is_staff or request.user.is_vendor):
            return JsonResponse({
                'status': 'error',
                'message': 'Unauthorized'
            }, status=401)
            
        subdomain = subdomain.replace('.platform', '')
        subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
        vendor = subdomain_obj.vendor
        
        # Start indexing task (this would ideally be async, but keeping it sync for simplicity)
        indexed_count = index_vendor_products(vendor.id)
        
        return JsonResponse({
            'status': 'success',
            'message': f'Successfully indexed {indexed_count} products',
            'indexed_count': indexed_count
        })
        
    except Exception as e:
        logger.error(f"Index products error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })
        



# Add this new view to manually index all products
@require_http_methods(["GET"])
def index_all_products_view(request, subdomain):
    """Index all products for a vendor"""
    try:
        subdomain = subdomain.replace('.platform', '')
        subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
        vendor = subdomain_obj.vendor
        
        # Initialize CLIP search
        from ai_features.clip_pineconesearch import CLIPPineconeSearch
        clip_search = CLIPPineconeSearch()
        
        # Get products with images
        from products.models import Product
        products = Product.objects.filter(
            vendor=vendor,
            product_images__isnull=False
        ).distinct()
        
        # Debug info
        product_count = products.count()
        
        results = {
            'vendor_id': vendor.id,
            'product_count': product_count,
            'indexed_products': [],
            'failed_products': []
        }
        
        # Index each product individually
        for product in products:
            try:
                # Check if product has images
                images = product.product_images.all()
                if not images.exists():
                    results['failed_products'].append({
                        'id': product.id,
                        'name': product.name,
                        'error': 'No images'
                    })
                    continue
                
                # Check if image file exists
                image_path = images.first().image.path
                if not os.path.exists(image_path):
                    results['failed_products'].append({
                        'id': product.id,
                        'name': product.name,
                        'error': 'Image file not found'
                    })
                    continue
                
                # Try to index
                success = clip_search.index_product(product)
                
                if success:
                    results['indexed_products'].append({
                        'id': product.id,
                        'name': product.name
                    })
                else:
                    results['failed_products'].append({
                        'id': product.id,
                        'name': product.name,
                        'error': 'Indexing failed'
                    })
            except Exception as e:
                results['failed_products'].append({
                    'id': product.id,
                    'name': product.name,
                    'error': str(e)
                })
        
        # Get Pinecone stats after indexing
        stats = clip_search.index.describe_index_stats()
        results['pinecone_vector_count'] = stats.total_vector_count
        
        return JsonResponse(results)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })
        
        
        
        
def test_recommendations(request, subdomain, product_id):
    """Debug view to test recommendations for a specific product"""
    try:
        subdomain = subdomain.replace('.platform', '')
        subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
        product = get_object_or_404(Product, id=product_id)
        
        from ai_features.recommendations import ContentBasedRecommender
        recommender = ContentBasedRecommender()
        
        # Set threshold
        threshold = 60.0
        
        # Get similar products
        similar_products = recommender.get_similar_products(
            product, 
            max_items=10,
            threshold=threshold
        )
        
        # Prepare results
        results = []
        for p in similar_products:
            results.append({
                'id': p.id,
                'name': p.name,
                'similarity_score': getattr(p, 'similarity_score', 0),
                'image_url': p.product_images.first().image.url if p.product_images.exists() else None,
            })
        
        return JsonResponse({
            'status': 'success',
            'product': {
                'id': product.id,
                'name': product.name,
            },
            'similar_products': results,
            'threshold': threshold
        })
    except Exception as e:
        import traceback
        return JsonResponse({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        })
        
        
        
        

import requests
import base64
import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

logger = logging.getLogger(__name__)  # Fixed from logger = logging.getLogger(name)

@csrf_exempt
def proxy_try_on(request):
    """Proxy the try-on request to the Google Colab server"""
    try:
        # Get the product image and name from the request
        product_image = request.POST.get('product_image')
        product_name = request.POST.get('product_name', 'Unknown Product')
        
        # Log the request (without the full image data for brevity)
        if product_image and len(product_image) > 100:
            logger.info(f"Received try-on request for {product_name}, image length: {len(product_image)}")
        else:
            logger.info(f"Received try-on request for {product_name}, but no valid image")
        
        # Check if the image is a base64 data URI
        if product_image and product_image.startswith('data:image'):
            # Extract the base64 part after the comma
            header, encoded = product_image.split(",", 1)  # Fixed from , encoded = product_image.split(",", 1)
            
            # The URL of your Flask server in Google Colab
            colab_url = "https://5000-gpu-t4-s-y5w38tbwdmiu-c.asia-southeast1-0.prod.colab.dev/try-on"
            
            # Prepare the data for the request
            data = {
                'product_name': product_name,
                'image_data': encoded
            }
            
            # Send the POST request to your Flask server
            response = requests.post(colab_url, json=data, timeout=30)
            
            # Check if the request was successful
            if response.status_code == 200:
                # If Colab returns HTML, just pass it through to the user
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' in content_type:
                    return HttpResponse(response.content, content_type=content_type)
                
                # Otherwise return the JSON response
                return JsonResponse(response.json())
            else:
                logger.error(f"Colab server returned error: {response.status_code}, {response.text}")
                return JsonResponse({
                    'status': 'error',
                    'message': f"Colab server error {response.status_code}: {response.text[:100]}"
                }, status=500)
        else:
            return JsonResponse({
                'status': 'error',
                'message': "Invalid image format. Please provide a base64-encoded image."
            }, status=400)
    except requests.exceptions.ConnectionError:
        logger.error("Connection error to Colab server")
        return JsonResponse({
            'status': 'error',
            'message': "Could not connect to the Colab server. It may be offline or the URL has changed."
        }, status=503)
    except Exception as e:
        logger.error(f"Error in proxy_try_on: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f"Server error: {str(e)}"
        }, status=500)