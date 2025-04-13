import random
from django.shortcuts import render, get_object_or_404, redirect
from .forms import ProductForm
from django.contrib.auth.decorators import login_required
from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import Subdomain
from .models import Product, Category, Cart, Wishlist, ColorVariant
from accounts.models import Vendor,VendorSetting ,Subdomain
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail

from django.http import JsonResponse, Http404
from ai_features import models  # Ensure ai_features module is imported
import json
from django.template.loader import render_to_string
import io
from django.views.decorators.http import require_http_methods

from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
from accounts.models import Vendor, Customer
from accounts.urls import urlpatterns
from accounts.views import customer_login



from functools import wraps
from django.shortcuts import redirect
from django.urls import reverse
from .models import Vendor
from accounts.views import vendor_login_required
from accounts.models import StorePhoto




@vendor_login_required
def vendor_home(request, subdomain):
    try:
        subdomain = subdomain.replace('.platform', '')
        subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
        vendor = subdomain_obj.vendor
        
        customer = request.customer
        
        customer = None
        if request.session.get('customer_id'):
            try:
                customer = Customer.objects.get(
                    id=request.session['customer_id'],
                    vendor=vendor
                )
                print(f"Found customer: {customer.email}")
            except Customer.DoesNotExist:
                print("Customer not found in database")
        
        # Get all products and new arrivals
        products = Product.objects.filter(vendor=vendor)
        new_arrivals = products.order_by('-created_at')[:8]
        
        from ai_features.services import get_recommended_products_for_homepage
        recommended_products = get_recommended_products_for_homepage(vendor)
        
        
        # Get store photos safely
        store_photos = StorePhoto.objects.filter(vendor=vendor).order_by('-is_primary', '-uploaded_at')
        store_photo = store_photos.first()  # Changed from [0] to first()
        # In vendor_home view

        context = {
            'vendor': vendor,
            'products': products,
            'customer': customer,
            'new_arrivals': new_arrivals,
            'recommended_products': recommended_products,
            'categories': Category.objects.filter(vendor=vendor),
            'cover_photos': vendor.settings.cover_photos.all().order_by('order'),
            'year': datetime.now().year,
            'show_popup': vendor.settings.show_popup,
            'popup_delay': vendor.settings.popup_delay,
            'debug': settings.DEBUG,
            'wishlisted_products': list(Wishlist.objects.filter(
                customer_id=request.session.get('customer_id', None)
            ).values_list('product_id', flat=True)),
            'total_products': products.count(),
            'total_customers': Customer.objects.filter(
                id__in=Order.objects.filter(vendor=vendor).values('customer_id')
            ).distinct().count(),
            'years_in_business': (timezone.now().year - vendor.date_joined.year),
            'store_photos': store_photo,  
        }
        
        if vendor.settings.instagram:
            instagram_posts = fetch_instagram_posts(vendor.settings.instagram)
            context['instagram_posts'] = instagram_posts
        
        return render(request, 'products/vendor_home.html', context)
        
    except Exception as e:
        # print(f"Error in vendor_home: {str(e)}")
        logger.error(f"Error in vendor_home: {str(e)}")
        messages.error(request, "An error occurred while loading the page")
        return redirect('accounts:customer_login' , subdomain=subdomain)
        # return redirect('products:vendor_home', subdomain=subdomain)





# Remove this decorator to allow guest access
# @vendor_login_required
# def vendor_home(request, subdomain):
#     try:
#         subdomain = subdomain.replace('.platform', '')
#         subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
#         vendor = subdomain_obj.vendor
        
#         # Remove this problematic line
#         # customer = request.customer
        
#         # This part is correct - get customer from session if available
#         customer = None
#         if request.session.get('customer_id'):
#             try:
#                 customer = Customer.objects.get(
#                     id=request.session['customer_id'],
#                     vendor=vendor
#                 )
#                 print(f"Found customer: {customer.email}")
#             except Customer.DoesNotExist:
#                 print("Customer not found in database")
        
#         # Get all products and new arrivals
#         products = Product.objects.filter(vendor=vendor)
#         new_arrivals = products.order_by('-created_at')[:8]
        
#         from ai_features.services import get_recommended_products_for_homepage
#         recommended_products = get_recommended_products_for_homepage(vendor)
        
#         # Get store photos safely
#         store_photos = StorePhoto.objects.filter(vendor=vendor).order_by('-is_primary', '-uploaded_at')
#         store_photo = store_photos.first()  # Changed from [0] to first()

#         context = {
#             'vendor': vendor,
#             'products': products,
#             'customer': customer,
#             'new_arrivals': new_arrivals,
#             'recommended_products': recommended_products,
#             'categories': Category.objects.filter(vendor=vendor),
#             'cover_photos': vendor.settings.cover_photos.all().order_by('order'),
#             'year': datetime.now().year,
#             'show_popup': vendor.settings.show_popup,
#             'popup_delay': vendor.settings.popup_delay,
#             'debug': settings.DEBUG,
#             'wishlisted_products': list(Wishlist.objects.filter(
#                 customer_id=request.session.get('customer_id', None)
#             ).values_list('product_id', flat=True)) if request.session.get('customer_id') else [],
#             'total_products': products.count(),
#             'total_customers': Customer.objects.filter(
#                 id__in=Order.objects.filter(vendor=vendor).values('customer_id')
#             ).distinct().count(),
#             'years_in_business': (timezone.now().year - vendor.date_joined.year),
#             'store_photos': store_photo,  
#         }
        
#         if vendor.settings.instagram:
#             instagram_posts = fetch_instagram_posts(vendor.settings.instagram)
#             context['instagram_posts'] = instagram_posts
        
#         return render(request, 'products/vendor_home.html', context)
        
#     except Exception as e:
#         logger.error(f"Error in vendor_home: {str(e)}")
#         messages.error(request, "An error occurred while loading the page")
#         # Fix the redirect loop by redirecting elsewhere on error
#         return redirect('products:product_list', subdomain=subdomain)



@receiver(post_save, sender=Vendor)
def create_vendor_settings(sender, instance, created, **kwargs):
    if created:
        VendorSetting.objects.create(
            vendor=instance,
            store_name=instance.first_name,
            primary_color='#007bff',
            secondary_color='#6c757d',
            accent_color='#28a745',
            heading_font='Roboto',
            body_font='Open Sans',
            announcement='Free Delivery over kathmandu valley',
            show_popup=False,
            popup_delay=3,
            contact_email='E-Platform@gmail.com',
            contact_phone='+977 9841602338',
            contact_address='Kalanki, Kathmandu'
        )



def product_detail(request, subdomain, slug):
    subdomain = subdomain.replace('.platform', '')
    subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
    vendor = subdomain_obj.vendor
    
    product = get_object_or_404(Product.objects.prefetch_related(
        'product_images',
        'color_variant',
        'size_variant'
    ), slug=slug, vendor=vendor)
    
    
    # Get similar products using AI-based recommendation
    similar_products = []
    try:
        from ai_features.recommendations import ContentBasedRecommender
        recommender = ContentBasedRecommender()
        similar_products = recommender.get_similar_products(product, threshold=60.0)
    except Exception as e:
        print(f"Error getting recommendations: {str(e)}")
    
    
    if similar_products:
        # Record recommendation events
        for position, rec_product in enumerate(similar_products):
            models.RecommendationEvent.objects.create(
                vendor=vendor,
                source_product=product,
                recommended_product=rec_product,
                recommendation_type='detail_page'
            )
    # If no AI recommendations, fall back to your existing related_products
    if not similar_products:
        similar_products = Product.objects.filter(
            category=product.category
        ).exclude(id=product.id)[:4]
    
    
    context = {
        'vendor': vendor,
        'product': product,
        'related_products': similar_products
    }
    return render(request, 'products/product_detail.html', context)


def product_list(request, subdomain):
    try:
        subdomain = subdomain.replace('.platform', '')
        subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
        vendor = subdomain_obj.vendor
        
        # Get customer from session if available
        customer = None
        if request.session.get('customer_id'):
            try:
                customer = Customer.objects.get(
                    id=request.session['customer_id'],
                    vendor=vendor
                )
            except Customer.DoesNotExist:
                pass
        
        # Get all products with filter options
        category_id = request.GET.get('category')
        sort_by = request.GET.get('sort', 'newest')
        
        products = Product.objects.filter(vendor=vendor)
        
        # Apply category filter if specified
        if category_id:
            try:
                category = Category.objects.get(id=category_id, vendor=vendor)
                products = products.filter(category=category)
            except Category.DoesNotExist:
                pass
        
        # Apply sorting
        if sort_by == 'price_low':
            products = products.order_by('price')
        elif sort_by == 'price_high':
            products = products.order_by('-price')
        else:  # default: newest
            products = products.order_by('-created_at')
        
        context = {
            'vendor': vendor,
            'products': products,
            'customer': customer,
            'categories': Category.objects.filter(vendor=vendor),
            'selected_category_id': category_id,
            'sort_by': sort_by,
            'wishlisted_products': list(Wishlist.objects.filter(
                customer_id=request.session.get('customer_id', None)
            ).values_list('product_id', flat=True))
        }
        
        return render(request, 'products/product_list.html', context)
        
    except Exception as e:
        print(f"Error in product_list: {str(e)}")
        messages.error(request, "An error occurred while loading the page")
        return redirect('products:vendor_home', subdomain=subdomain)


@login_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.vendor = request.user
            product.save()
            return redirect('products:product_list')
    else:
        form = ProductForm()
    return render(request, 'products/product_form.html', {'form': form})





def cart_count(request):
    if request.session.get('customer_id'):
        cart_count = Cart.objects.filter(customer_id=request.session['customer_id']).count()
        wishlist_count = Wishlist.objects.filter(customer_id=request.session['customer_id']).count()
        return {
            'cart_count': cart_count,
            'wishlist_count': wishlist_count
        }
    return {'cart_count': 0, 'wishlist_count': 0}


 

# Add this import at the top with other imports
from django.db.models import Sum, F

# Update the cart_view function
def cart_view(request, subdomain):
    subdomain = subdomain.replace('.platform', '')
    subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
    vendor = subdomain_obj.vendor
    
    try:
        customer = get_object_or_404(Customer, id=request.session.get('customer_id'))
        cart_items = Cart.objects.filter(customer=customer, vendor=vendor)
        
        # Calculate subtotal using F() expression
        subtotal = cart_items.aggregate(
            total=Sum(F('product__price') * F('quantity'))
        )['total'] or 0
        
        context = {
            'cart_items': cart_items,
            'subtotal': subtotal,
            'total': subtotal,  # Add shipping calculation here if needed
            'vendor': vendor,
            'customer': customer
        }
        
        return render(request, 'products/cart.html', context)
    
    except Customer.DoesNotExist:
        messages.error(request, "Please login to view your cart")
        return redirect('accounts:customer_login', subdomain=subdomain)


from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import Cart, Product
from accounts.models import Customer
import json

def add_to_cart(request):
    if not request.session.get('customer_id'):
        return JsonResponse({
            'status': 'error',
            'message': 'Please login first'
        }, status=401)

    if request.method == 'POST':
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
        color_id = data.get('color_id')
        size_id = data.get('size_id')
        
        try:
            customer = get_object_or_404(Customer, id=request.session['customer_id'])
            product = get_object_or_404(Product, id=product_id)
            
            cart_item, created = Cart.objects.get_or_create(
                customer=customer,
                product=product,
                vendor=product.vendor,
                color_id=color_id,
                size_id=size_id,
                defaults={'quantity': quantity}
            )
            
            if not created:
                cart_item.quantity += quantity
                cart_item.save()
            
            cart_count = Cart.objects.filter(customer=customer).count()
            
            return JsonResponse({
                'status': 'success',
                'cart_count': cart_count,
                'message': 'Added to cart successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'status': 'error'}, status=400)


@require_http_methods(["POST"])
def update_cart(request):
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        action = data.get('action')
        
        cart_item = get_object_or_404(Cart, id=item_id, customer_id=request.session.get('customer_id'))
        
        # Check stock limit
        if action == 'increase':
            product_stock = cart_item.product.stock
            if cart_item.quantity >= product_stock:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Cannot add more items. Only {product_stock} available in stock.'
                })
        
        # Process quantity changes
        if action == 'increase':
            cart_item.quantity += 1
        elif action == 'decrease':
            cart_item.quantity -= 1
            if cart_item.quantity <= 0:
                cart_item.delete()
                
                # Recalculate totals after deletion
                customer = cart_item.customer
                cart_items = Cart.objects.filter(customer=customer)
                subtotal = sum(item.total_price for item in cart_items)
                
                return JsonResponse({
                    'status': 'success',
                    'quantity': 0,
                    'item_total': 0,
                    'cart_count': cart_items.count(),
                    'subtotal': float(subtotal),
                    'total': float(subtotal)
                })
        
        # Save changes
        cart_item.save()
        
        # Get updated cart info
        customer = cart_item.customer
        cart_items = Cart.objects.filter(customer=customer)
        subtotal = sum(item.total_price for item in cart_items)
        
        return JsonResponse({
            'status': 'success',
            'quantity': cart_item.quantity,
            'item_total': float(cart_item.total_price),
            'cart_count': cart_items.count(),
            'subtotal': float(subtotal),
            'total': float(subtotal)
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error', 
            'message': f'Error: {str(e)}'
        })


def remove_from_cart(request, item_id):
    if request.method == 'POST':
        try:
            cart_item = Cart.objects.get(id=item_id)
            customer = cart_item.customer
            cart_item.delete()
            
            # Recalculate totals after deletion
            cart_items = Cart.objects.filter(customer=customer)
            subtotal = sum(item.total_price for item in cart_items)
            
            return JsonResponse({
                'status': 'success',
                'cart_count': cart_items.count(),
                'subtotal': float(subtotal),
                'total': float(subtotal),  # Add shipping/tax calculations if needed
                'message': 'Item removed successfully'
            })
            
        except Cart.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Cart item not found'
            }, status=404)
            
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=400)





# wish list implementation

def wishlist_view(request, subdomain):
    subdomain = subdomain.replace('.platform', '')
    subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
    vendor = subdomain_obj.vendor
    
    try:
        customer = get_object_or_404(Customer, id=request.session.get('customer_id'))
        wishlist_items = Wishlist.objects.filter(customer=customer, vendor=vendor)
        
        context = {
            'wishlist_items': wishlist_items,
            'vendor': vendor,
            'customer': customer
        }
        
        return render(request, 'products/wishlist.html', context)
    
    except Customer.DoesNotExist:
        messages.error(request, "Please login to view your wishlist")
        return redirect('accounts:customer_login', subdomain=subdomain)



from django.http import JsonResponse
import json

@require_http_methods(["POST"])
def toggle_wishlist(request):
    """Toggle product in wishlist"""
    # Change this:
    # if not request.user.is_authenticated:
    
    # To this:
    if not request.session.get('customer_id'):
        return JsonResponse({'status': 'error', 'message': 'Login required'}, status=401)
    
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        product = get_object_or_404(Product, id=product_id)
        
        # Get customer from session (NOT from request.user)
        customer = get_object_or_404(Customer, id=request.session.get('customer_id'))
        
        # Check if product is already in wishlist
        wishlist_item = Wishlist.objects.filter(customer=customer, product=product).first()
        
        if wishlist_item:
            # Remove from wishlist
            wishlist_item.delete()
            message = f"{product.name} removed from wishlist"
            added = False
        else:
            # Add to wishlist
            Wishlist.objects.create(customer=customer, product=product, vendor=product.vendor)
            message = f"{product.name} added to wishlist"
            added = True
            
        # Get updated wishlist count
        wishlist_count = Wishlist.objects.filter(customer=customer).count()
            
        return JsonResponse({
            'status': 'success', 
            'message': message, 
            'added': added,
            'wishlist_count': wishlist_count
        })
        
    except Exception as e:
        logger.error(f"Error in toggle_wishlist: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)})










#place order and send email confirmation

from .models import Order, OrderItem, DeliveryAddress, Cart
from .utils import EsewaPayment
from django.http import JsonResponse
from django.urls import reverse
from accounts.models import Customer
import json
import logging
from accounts.views import create_order_notification
logger = logging.getLogger(__name__)

from django.http import JsonResponse
from django.db import transaction
from django.shortcuts import get_object_or_404
import json

def place_order(request, subdomain):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    try:
        # Get customer from session
        customer_id = request.session.get('customer_id')
        if not customer_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Please login to continue'
            }, status=401)

        # Get vendor from subdomain
        subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
        vendor = subdomain_obj.vendor
        
        # Parse request data
        data = json.loads(request.body)
        payment_method = data.get('payment_method')
        address_id = data.get('address_id')
        new_address = data.get('new_address')
        is_buy_now = data.get('is_buy_now', False)

        with transaction.atomic():
            # Handle delivery address
            if address_id:
                delivery_address = get_object_or_404(
                    DeliveryAddress, 
                    id=address_id, 
                    customer_id=customer_id
                )
            else:
                # Create new address
                delivery_address = DeliveryAddress.objects.create(
                    customer_id=customer_id,
                    full_name=new_address['full_name'],
                    phone_number=new_address['phone_number'],
                    street_address=new_address['street_address'],
                    city=new_address['city'],
                    state=new_address['state'],
                    postal_code=new_address['postal_code'],
                    is_default=new_address.get('save_address', False)
                )

            # Set initial order status based on payment method
            initial_status = 'pending_payment' if payment_method == 'esewa' else 'pending'

            # Process either buy now or cart checkout
            if is_buy_now:
                # Get buy now data from session
                buy_now_data = request.session.get('buy_now_data')
                if not buy_now_data:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'No product selected for purchase'
                    })
                    
                # Get product
                product = get_object_or_404(Product, id=buy_now_data['product_id'])
                
                # Calculate total
                quantity = int(buy_now_data.get('quantity', 1))
                total_amount = product.price * quantity
                
                # Create order with proper initial status
                order = Order.objects.create(
                    customer_id=customer_id,
                    vendor=vendor,
                    delivery_address=delivery_address,
                    payment_method=payment_method,
                    status=initial_status,
                    total_amount=total_amount
                )
                
                # Create order item
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    color_id=buy_now_data.get('color_id'),
                    size_id=buy_now_data.get('size_id'),
                    price=product.price
                )
                
                # Clear buy now data from session
                del request.session['buy_now_data']
                request.session.modified = True
                
            else:
                # Original cart checkout logic
                cart_items = Cart.objects.filter(
                    customer_id=customer_id,
                    vendor=vendor
                ).select_related('product')

                if not cart_items.exists():
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Your cart is empty'
                    })

                # Calculate total
                total_amount = sum(item.total_price for item in cart_items)

                # Create order with proper initial status
                order = Order.objects.create(
                    customer_id=customer_id,
                    vendor=vendor,
                    delivery_address=delivery_address,
                    payment_method=payment_method,
                    status=initial_status,
                    total_amount=total_amount
                )

                # Create order items
                order_items = []
                for cart_item in cart_items:
                    order_items.append(OrderItem(
                        order=order,
                        product=cart_item.product,
                        quantity=cart_item.quantity,
                        color=cart_item.color,
                        size=cart_item.size,
                        price=cart_item.product.price
                    ))
                OrderItem.objects.bulk_create(order_items)

                # Only clear cart for COD orders or after successful payment
                if payment_method == 'cod':
                    cart_items.delete()
            
            # Only create notification for confirmed orders
            if payment_method == 'cod':
                create_order_notification(request, order)

            # Handle payment methods
            if payment_method == 'cod':
                return JsonResponse({
                    'status': 'success',
                    'message': 'Order placed successfully',
                    'payment_method': 'cod',
                    'redirect_url': reverse('products:order_confirmation', kwargs={
                        'subdomain': subdomain,
                        'order_id': order.order_id
                    })
                })
                
            elif payment_method == 'esewa':
                # Store order ID in session to process after payment
                request.session['pending_esewa_order_id'] = order.order_id
                request.session.modified = True
                
                esewa = EsewaPayment()
                payment_url, params = esewa.generate_payment_data(order)
                return JsonResponse({
                    'status': 'success',
                    'payment_method': 'esewa',
                    'redirect_url': payment_url,
                    'params': params
                })
            
    except Exception as e:
        logger.error(f"Order placement error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        }, status=500)
    
    

def send_order_confirmation(order):
    subject = f'Order Confirmation - {order.order_id}'
    html_message = render_to_string('emails/order_confirmation.html', {
        'order': order
    })
    
    send_mail(
        subject=subject,
        message='',
        html_message=html_message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[order.customer.email]
    )






#esewa payment confirmation

from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from .utils import EsewaPayment
from .models import Order, Payment

def initiate_esewa_payment(request, order_id):
    try:
        # Get the order with vendor information
        order = get_object_or_404(Order.objects.select_related('vendor'), order_id=order_id)
        
        # Make sure the vendor is available
        vendor = order.vendor
        
        # Generate payment data
        esewa = EsewaPayment()
        payment_url, params = esewa.generate_payment_data(order)
        
        # Store payment attempt
        Payment.objects.create(
            order=order,
            payment_method='esewa',
            amount=order.total_amount,
            status='pending'
        )
        
        context = {
            'order': order,
            'vendor': vendor,  # Include the vendor in context
            'esewa_url': payment_url,
            'params': params
        }
        
        return render(request, 'products/redirect.html', context)
        
    except Order.DoesNotExist:
        messages.error(request, "Order not found")
        return redirect('products:vendor_home', subdomain=request.subdomain)
    

# 
@require_http_methods(["GET"])
def get_payment_details(request, order_id):
    try:
        # Get the order
        order = get_object_or_404(Order, order_id=order_id)
        
        # Ensure order belongs to the current customer
        customer_id = request.session.get('customer_id')
        if not customer_id or order.customer_id != int(customer_id):
            return JsonResponse({
                'status': 'error', 
                'message': "You don't have permission to access this order"
            }, status=403)
        
        # Generate eSewa payment data
        esewa = EsewaPayment()
        payment_url, params = esewa.generate_payment_data(order)
        
        return JsonResponse({
            'status': 'success',
            'order': {
                'order_id': order.order_id,
                'total_amount': float(order.total_amount)
            },
            'esewa_url': payment_url,
            'params': params
        })
        
    except Order.DoesNotExist:
        return JsonResponse({
            'status': 'error', 
            'message': "Order not found"
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error', 
            'message': str(e)
        }, status=500)


import json
import base64
from django.shortcuts import redirect
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from .models import Order, Payment
from accounts.models import Vendor

@csrf_exempt
def esewa_payment_success(request):
    try:
        # Get and decode the response data
        encoded_data = request.GET.get('data', '')
        decoded_data = json.loads(base64.b64decode(encoded_data))
        
        # Extract required fields
        transaction_uuid = decoded_data.get('transaction_uuid')
        status = decoded_data.get('status')
        transaction_code = decoded_data.get('transaction_code')
        
        # Extract original order ID from transaction UUID (example: ORD-123-456-789)
        # Transaction UUIDs may contain the order ID plus extra identifiers
        original_order_id = None
        if transaction_uuid:
            # Try to extract just the order ID portion from the transaction UUID
            parts = transaction_uuid.split('-')
            if len(parts) >= 3:
                # First part is likely "ORD"
                original_order_id = f"{parts[0]}-{parts[1]}-{parts[2]}"
        
        if status == 'COMPLETE':
            try:
                # First try with the original extracted order ID
                if original_order_id:
                    try:
                        order = Order.objects.get(order_id=original_order_id)
                    except Order.DoesNotExist:
                        # If that doesn't work, try with the full transaction UUID
                        order = Order.objects.get(order_id=transaction_uuid)
                else:
                    # If no original order ID could be extracted, use the full UUID
                    order = Order.objects.get(order_id=transaction_uuid)
                
                # Get vendor and subdomain from the order
                vendor = order.vendor
                subdomain_obj = vendor.subdomain
                subdomain = subdomain_obj.subdomain if subdomain_obj else 'default'
                
                # Create payment record
                Payment.objects.create(
                    order=order,
                    payment_method='esewa',
                    amount=order.total_amount,
                    status='completed',
                    transaction_id=transaction_code,
                    payment_response=decoded_data
                )
                
                # Update order status
                order.payment_status = True
                order.status = 'pending'  # Now set to pending since payment is complete
                order.save()
                
                # Now create the notification since payment is confirmed
                create_order_notification(request, order)
                
                # For cart orders, delete the cart items now that payment is complete
                if not request.session.get('buy_now_data'):
                    Cart.objects.filter(customer=order.customer, vendor=order.vendor).delete()
                
                messages.success(request, "Payment successful!")
                return redirect(f'/{subdomain}.platform/order/confirmation/{order.order_id}/')
                
            except Order.DoesNotExist:
                messages.error(request, "Order not found")
                # Use a simple redirect when subdomain is not available
                return redirect('/')
                
        else:
            messages.error(request, "Payment was not completed")
            # Use a simple redirect when subdomain is not available
            return redirect('/')
            
    except Exception as e:
        logger.error(f"eSewa payment error: {str(e)}")
        messages.error(request, "An error occurred processing the payment")
        # Use a simple redirect when subdomain is not available  
        return redirect('/')
    
    

@csrf_exempt
def esewa_payment_failure(request):
    # Get the pending order ID from session
    if order_id := request.session.get('pending_esewa_order_id'):
        try:
            # Find the order
            order = Order.objects.get(order_id=order_id)
            
            # Get subdomain from order's vendor
            subdomain = order.vendor.subdomain.subdomain if order.vendor.subdomain else 'default'
            
            # Change status to payment failed
            order.status = 'payment_failed'
            order.save()
            
            # Clear the pending order from session
            del request.session['pending_esewa_order_id']
            request.session.modified = True
            
            messages.error(request, "Payment failed or was cancelled")
            return redirect('products:vendor_home', subdomain=subdomain)
            
        except Order.DoesNotExist:
            pass
    
    # Fallback to homepage if order not found or no pending order
    return redirect('/')


def generate_payment_data(self, order):
    # Format amount to 2 decimal places
    amount = "{:.2f}".format(float(order.total_amount))
    
    # Use the original order ID as the transaction UUID for easier lookup
    # Append timestamp to ensure uniqueness if needed
    transaction_uuid = order.order_id  # Just use the exact order ID
    
    # Store order ID in session for reference
    if hasattr(order, 'request') and order.request:
        order.request.session['pending_esewa_order_id'] = order.order_id
        order.request.session.modified = True
    
    # Generate payment data
    params = {
        'amount': amount,
        'tax_amount': "0",
        'total_amount': amount,  # Same as amount if no tax
        'transaction_uuid': transaction_uuid,
        'product_code': self.merchant_id,
        'product_service_charge': "0",
        'product_delivery_charge': "0",
        'success_url': self.success_url,
        'failure_url': self.failure_url,
        'signed_field_names': "total_amount,transaction_uuid,product_code",
    }
    
    # Generate signature
    params['signature'] = self.generate_signature(
        total_amount=amount,
        transaction_uuid=transaction_uuid,
        product_code=self.merchant_id
    )
    
    return self.test_url, params

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Cart, Order



@vendor_login_required
def checkout_view(request, subdomain):
    # Remove .platform from subdomain if present
    subdomain = subdomain.replace('.platform', '')
    
    # Check if customer is logged in
    customer_id = request.session.get('customer_id')
    if not customer_id:
        messages.error(request, "Please login to checkout")
        return redirect('accounts:customer_login', subdomain=subdomain)
    
    try:
        # Get vendor by subdomain using the Subdomain model
        subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
        vendor = subdomain_obj.vendor
        customer = Customer.objects.get(id=customer_id)
        cart_items = Cart.objects.filter(customer=customer)
        
        if not cart_items.exists():
            messages.warning(request, "Your cart is empty")
            return redirect('products:cart', subdomain=subdomain)
        
        context = {
            'cart_items': cart_items,
            'subtotal': sum(item.total_price for item in cart_items),
            'total': sum(item.total_price for item in cart_items),  # Add shipping if needed
            'vendor': vendor,
            'saved_addresses': DeliveryAddress.objects.filter(customer=customer)
        }
        
        return render(request, 'products/checkout.html', context)
        
    except (Subdomain.DoesNotExist, Customer.DoesNotExist) as e:
        messages.error(request, "An error occurred")
        return redirect('products:cart', subdomain=subdomain)
    
   
   
@vendor_login_required
def buy_now_checkout(request, subdomain):
    try:
        # Clean subdomain
        subdomain = subdomain.replace('.platform', '')
        subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
        vendor = subdomain_obj.vendor
        
        # Check customer login
        customer_id = request.session.get('customer_id')
        if not customer_id:
            messages.error(request, "Please login to checkout")
            return redirect('accounts:customer_login', subdomain=subdomain)
            
        customer = get_object_or_404(Customer, id=customer_id)
        
        # Get buy now data
        buy_now_data = request.session.get('buy_now_data')
        if not buy_now_data:
            messages.error(request, "No product selected for purchase")
            return redirect('products:vendor_home', subdomain=subdomain)
            
        # Get product details
        product = get_object_or_404(Product, id=buy_now_data['product_id'])
        
        # Get selected color and size if they exist
        selected_color = None
        selected_size = None
        
        if buy_now_data.get('color_id'):
            try:
                selected_color = ColorVariant.objects.get(id=buy_now_data['color_id'])
            except ColorVariant.DoesNotExist:
                pass
                
        if buy_now_data.get('size_id'):
            try:
                selected_size = SizeVariant.objects.get(id=buy_now_data['size_id'])
            except:
                pass
                
        # Calculate total
        quantity = buy_now_data.get('quantity', 1)
        total = product.price * int(quantity)
        
        context = {
            'vendor': vendor,
            'customer': customer,
            'is_buy_now': True,
            'saved_addresses': DeliveryAddress.objects.filter(customer=customer),
            'buy_now_data': buy_now_data,
            'product': product,
            'selected_color': selected_color,
            'selected_size': selected_size,
            'total': total,
            'subtotal': total
        }
        
        return render(request, 'products/checkout.html', context)
        
    except Exception as e:
        print(f"Buy now error: {str(e)}")
        messages.error(request, "An error occurred")
        return redirect('products:vendor_home', subdomain=subdomain)
    
    
    
    
    
@require_http_methods(["POST"])
def store_buy_now_data(request):
    try:
        data = json.loads(request.body)
        request.session['buy_now_data'] = data
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


    
    
def order_confirmation(request, subdomain, order_id):
    try:
        # Clean subdomain
        subdomain = subdomain.replace('.platform', '')
        
        # Get vendor through Subdomain model
        subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
        vendor = subdomain_obj.vendor
        
        # Get order
        order = get_object_or_404(Order, order_id=order_id)
        
        # Verify order belongs to vendor
        if order.vendor != vendor:
            messages.error(request, "Invalid order")
            return redirect('products:cart', subdomain=subdomain)
        
        context = {
            'order': order,
            'vendor': vendor,
            'items': order.items.all()
        }
        
        return render(request, 'products/order_confirmation.html', context)
        
    except Exception as e:
        logger.error(f"Order confirmation error: {str(e)}")
        messages.error(request, "Order not found")
        return redirect('products:cart', subdomain=subdomain)





from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from accounts.models import Customer, Subdomain
from .models import Order

@vendor_login_required 
def orders_list(request, subdomain):
    try:
        # Clean subdomain
        subdomain = subdomain.replace('.platform', '')
        subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
        vendor = subdomain_obj.vendor
        
        # Get customer from session
        customer_id = request.session.get('customer_id')
        if not customer_id:
            messages.error(request, "Please login to view your orders")
            return redirect('accounts:customer_login', subdomain=subdomain)
            
        customer = get_object_or_404(Customer, id=customer_id)
        
        # Get all orders
        orders = Order.objects.filter(
            customer=customer,
            vendor=vendor
        ).exclude(
            status='pending_payment'  # Don't show orders with pending payments
        ).order_by('-created_at').prefetch_related('items', 'items__product', 'items__product__product_images')
        
        
        pending_payment_orders = Order.objects.filter(
            customer=customer,
            vendor=vendor,
            status='pending_payment'
        ).order_by('-created_at')
        
        context = {
            'orders': orders,
            'pending_payment_orders': pending_payment_orders,
            'vendor': vendor,
            'customer': customer,
            'recent_order': orders.first() if orders.exists() else None
        }
        
        return render(request, 'products/orders.html', context)
        
    except Exception as e:
        messages.error(request, "An error occurred while loading your orders")
        return redirect('products:vendor_home', subdomain=subdomain)
    
    
    


from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from .models import Order
from accounts.models import Customer


def order_detail(request, subdomain, order_id):
    try:
        # Clean subdomain and get vendor
        subdomain = subdomain.replace('.platform', '')
        subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
        vendor = subdomain_obj.vendor
        
        # Check if customer is logged in
        customer_id = request.session.get('customer_id')
        if not customer_id:
            messages.error(request, "Please login to view order details")
            return redirect('accounts:customer_login', subdomain=subdomain)
        
        # Get customer
        customer = get_object_or_404(Customer, id=customer_id)
        
        # Get order with related data
        order = Order.objects.select_related(
            'delivery_address', 'customer', 'vendor'
        ).prefetch_related(
            'items',
            'items__product',
            'items__product__product_images'
        ).get(
            order_id=order_id,
            customer=customer,
            vendor=vendor
        )
        
        # Set cancel_deadline if it's not set
        if not order.cancel_deadline:
            order.cancel_deadline = order.created_at + timedelta(hours=24)
            order.save()
        
        # Check if order can be cancelled
        can_cancel = (
            order.status in ['pending', 'processing'] 
            and not order.shipping_started 
            and timezone.now() < order.cancel_deadline
        )
        
        context = {
            'order': order,
            'vendor': vendor,
            'customer': customer,
            'can_cancel': can_cancel,
            'items': order.items.all(),
            'time_left_for_cancel': order.time_left_for_cancel
        }
        
        return render(request, 'products/order_details.html', context)
        
    except Order.DoesNotExist:
        messages.error(request, "Order not found")
        return redirect('products:orders', subdomain=subdomain)
    except Exception as e:
        logger.error(f"Order detail error: {str(e)}")
        messages.error(request, "An error occurred while loading order details")
        return redirect('products:orders', subdomain=subdomain)



def cancel_order(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    try:
        # Get customer from session
        customer_id = request.session.get('customer_id')
        if not customer_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Please login to continue'
            }, status=401)
        
        # Get order and verify ownership
        order = get_object_or_404(Order, 
            order_id=order_id, 
            customer_id=customer_id
        )
        
        # Check if order can be cancelled
        if not order.can_cancel():
            return JsonResponse({
                'status': 'error',
                'message': 'Order cannot be cancelled'
            })
        
        # Process cancellation
        order.status = 'cancelled'
        order.cancelled_at = timezone.now()
        order.save()
        
        messages.success(request, 'Order cancelled successfully')
        return JsonResponse({
            'status': 'success',
            'message': 'Order cancelled successfully'
        })
        
    except Order.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Order not found'
        })
    except Exception as e:
        logger.error(f"Cancel order error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'An error occurred while cancelling the order'
        })


@require_http_methods(["POST"])
def delete_order(request, order_id):
    try:
        print(f"Attempting to delete order: {order_id}")
        
        # Get customer from session
        customer_id = request.session.get('customer_id')
        if not customer_id:
            print("No customer ID in session")
            return JsonResponse({
                'status': 'error',
                'message': 'Please login to continue'
            }, status=401)
            
        print(f"Customer ID: {customer_id}")
        
        # Get the order
        order = get_object_or_404(Order, order_id=order_id, customer_id=customer_id)
        print(f"Order found: {order}, status: {order.status}")
        
        # Check if order can be deleted
        if order.status not in ['pending_payment', 'cancelled']:
            print(f"Order status not eligible for deletion: {order.status}")
            return JsonResponse({
                'status': 'error',
                'message': 'Only cancelled or pending payment orders can be deleted'
            }, status=400)
            
        # Delete the order
        order.delete()
        print("Order deleted successfully")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Order deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting order: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)
  
        

def customer_dashboard(request, subdomain):
    customer_id = request.session.get('customer_id')
    if not customer_id:
        return redirect('accounts:customer_login', subdomain=subdomain)
    
    customer = get_object_or_404(Customer, id=customer_id)
    
    # Get vendor from subdomain
    subdomain = subdomain.replace('.platform', '')
    subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
    vendor = subdomain_obj.vendor

    # Get order statistics
    total_orders = Order.objects.filter(customer_id=customer_id).count()
    completed_orders = Order.objects.filter(customer_id=customer_id, status='delivered').count()
    active_orders = Order.objects.filter(customer_id=customer_id, status__in=['pending', 'processing', 'shipped']).count()
    
    # Get recent orders
    recent_orders = Order.objects.filter(customer_id=customer_id).order_by('-created_at')[:5]
    
    # Get wishlist count
    wishlist_count = Wishlist.objects.filter(customer_id=customer_id).count()
    
    # Get total spent
    total_spent = Order.objects.filter(
        customer_id=customer_id, 
        status='delivered'
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    context = {
        'customer': customer,
        'total_orders': total_orders,
        'completed_orders': completed_orders,
        'active_orders': active_orders,
        'recent_orders': recent_orders,
        'wishlist_count': wishlist_count,
        'total_spent': total_spent,
        'vendor': vendor,
    }
    
    return render(request, 'accounts/customer_dashboard.html', context)




#search products
from django.db.models import Q
from django.core.paginator import Paginator

def search_products(request, subdomain):
    """Search products based on query parameters"""
    import re
    from django.http import Http404
    
    subdomain = subdomain.replace('.platform', '')
    sanitized_subdomain = re.sub(r'[^a-z0-9-]', '', subdomain.lower())
    
    try:
        # Try sanitized subdomain first
        subdomain_obj = get_object_or_404(Subdomain, subdomain=sanitized_subdomain)
    except Http404:
        # Fallback handling
        raise Http404(f"Invalid subdomain: {sanitized_subdomain}")
        
    vendor = subdomain_obj.vendor
    
    # Get filter parameters
    query = request.GET.get('q', '')
    selected_categories = request.GET.get('categories', '').split(',')
    selected_categories = [cat for cat in selected_categories if cat.strip()]
    price_max = request.GET.get('price')
    sort = request.GET.get('sort', 'relevance')
    
    # Get max price for filter
    max_price = Product.objects.filter(vendor=vendor).order_by('-price').first()
    max_price = max_price.price if max_price else 1000
    
    # Check if this is an image search
    is_image_search = request.GET.get('type') == 'image'
    
    if is_image_search:
        # Get search results from session
        search_results = request.session.get('image_search_results', [])
        
        if search_results:
            # Get product IDs and similarity scores
            product_data = {int(float(item['product_id'])): item['similarity_score'] 
                          for item in search_results if 'product_id' in item}
            product_ids = list(product_data.keys())
            
            # Query the database for these products
            products = Product.objects.filter(id__in=product_ids, vendor=vendor)
            
            # Apply category filter if selected
            if selected_categories:
                products = products.filter(category__id__in=selected_categories)
            
            # Apply price filter if specified
            if price_max:
                products = products.filter(price__lte=price_max)
                
            # Apply sorting
            if sort == 'price_asc':
                products = products.order_by('price')
            elif sort == 'price_desc':
                products = products.order_by('-price')
            elif sort == 'newest':
                products = products.order_by('-created_at')
            # Default to similarity score for relevance in image search
                
            # After filtering, attach similarity scores to products
            for product in products:
                product.similarity_score = product_data.get(product.id, 0)
                
            # If sorting by relevance, sort by similarity score
            if sort == 'relevance' or not sort:
                products = sorted(products, key=lambda p: p.similarity_score, reverse=True)
        else:
            products = Product.objects.none()
    else:
        # Regular text search - Base queryset
        products = Product.objects.filter(vendor=vendor)
        
        # Apply search query
        if query:
            products = products.filter(
                Q(name__icontains=query) | 
                Q(description__icontains=query) |
                Q(category__category_name__icontains=query)
            ).distinct()
        
        # Apply category filter
        if selected_categories:
            products = products.filter(category__id__in=selected_categories)
        
        # Apply price filter
        if price_max:
            products = products.filter(price__lte=price_max)
        
        # Apply sorting
        if sort == 'price_asc':
            products = products.order_by('price')
        elif sort == 'price_desc':
            products = products.order_by('-price')
        elif sort == 'newest':
            products = products.order_by('-created_at')
    
    context = {
        'products': products,
        'query': query,
        'categories': Category.objects.filter(vendor=vendor),
        'selected_categories': selected_categories,
        'max_price': max_price,
        'selected_price': price_max,
        'sort': sort,
        'vendor': vendor,
        'is_image_search': is_image_search
    }
    
    return render(request, 'products/search_result.html', context)





#image search


from .vector_database import VectorDatabase
from PIL import Image
import io
from .vector_database import VectorDatabase
from ai_features.clip_pineconesearch import CLIPPineconeSearch
from ai_features.recommendations import ContentBasedRecommender




# Import new stuff with error handling
# Don't initialize at import time
vector_db = None

def get_vector_db():
    global vector_db
    if vector_db is None:
        try:
            vector_db = CLIPPineconeSearch()
        except Exception as e:
            logger.error(f"Error initializing vector_db: {str(e)}")
    return vector_db

try:
    recommender_system = ContentBasedRecommender()
except Exception as e:
    logger.error(f"Failed to initialize recommendation system: {str(e)}")
    recommender_system = None
    
    
from io import BytesIO
@require_http_methods(["POST"])
def image_search_view(request, subdomain):
    try:
        if 'image_query' not in request.FILES:
            return JsonResponse({
                'status': 'error', 
                'message': 'No image file provided'
            })
            
        # Import here to ensure it's available
        from ai_features.clip_pineconesearch import CLIPPineconeSearch
        
        subdomain = subdomain.replace('.platform', '')
        subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
        vendor = subdomain_obj.vendor
        
        print(f"Processing image search for vendor {vendor.id}")
        
        # Process query image
        image_file = request.FILES['image_query']
        img = Image.open(BytesIO(image_file.read())).convert('RGB')
        
        # Use CLIP search
        clip_search = CLIPPineconeSearch()
        search_results = []
           
        # Set threshold to 60% for high relevance
        threshold = 60.0
        
        # Initialize clip_search if not already defined
        if 'clip_search' not in globals():
            try:
                from ai_features.clip_pineconesearch import CLIPPineconeSearch
                clip_search = CLIPPineconeSearch()
            except Exception as e:
                logger.error(f"Error initializing clip_search: {str(e)}")
                clip_search = None

        if clip_search:
            try:
                # Check Pinecone stats first
                stats = clip_search.index.describe_index_stats()
                print(f"Pinecone has {stats.total_vector_count} vectors")
                
                # Search with threshold
                search_results = clip_search.search(
                    vendor.id, 
                    query_image=img, 
                    threshold=threshold
                )
                print(f"CLIP search returned {len(search_results)} results above {threshold}% similarity")
                
                # If no results and no vectors, try indexing
                if not search_results and stats.total_vector_count == 0:
                    print(f"No vectors found, indexing products for vendor {vendor.id}")
                    indexed_count = clip_search.index_vendor_products(vendor.id)
                    print(f"Indexed {indexed_count} products")
                    
                    # Try search again
                    search_results = clip_search.search(
                        vendor.id, 
                        query_image=img,
                        threshold=threshold
                    )
                    print(f"After indexing: search returned {len(search_results)} results")
            except Exception as e:
                print(f"CLIP search error: {str(e)}")
                
                # Fall back to ResNet search
                if vector_db:
                    try:
                        search_results = vector_db.search_by_image(vendor.id, img)
                        # Filter results below threshold
                        search_results = [r for r in search_results if r.get('similarity_score', 0) >= threshold]
                        print(f"Fallback ResNet search returned {len(search_results)} results")
                    except Exception as e:
                        print(f"ResNet search error: {str(e)}")
        
        if not search_results:
            return JsonResponse({
                'status': 'error',
                'message': 'No similar products found'
            })
        
        # Debug search results
        print(f"Search results: {search_results}")
        
        # Store results in session
        request.session['image_search_results'] = search_results
        
        return JsonResponse({
            'status': 'success',
            'redirect_url': reverse('products:search', kwargs={'subdomain':subdomain}) + '?type=image',
            'result_count': len(search_results)
        })
        
    except Http404:
        return JsonResponse({
            'status': 'error', 
            'message': 'Invalid subdomain'
        })
        
    except Exception as e:
        print(f"Image search error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })
  
  



def fetch_instagram_posts(instagram_handle):
    """Fetch Instagram posts using Instagram Basic Display API"""
    try:
        # For now, return placeholder data since API access is failing
        return [
            {
                'id': f'placeholder-{i}',
                'image_url': f'https://source.unsplash.com/random/600x600?fashion&sig={i}',
                'link': instagram_handle or 'https://instagram.com',
                'likes': random.randint(10, 100),
                'comments': random.randint(1, 20),
                'caption': f'Check out our latest collection! #{i}'
            } for i in range(6)
        ]
    except Exception as e:
        print(f"Instagram fetch error: {e}")
        return []
    
    


def index_vendor_products(self, vendor_id):
    """Index all products for a specific vendor"""
    try:
        # Get vendor's products with images
        products = Product.objects.filter(
            vendor_id=vendor_id,
            product_images__isnull=False
        ).distinct()
        
        total_count = products.count()
        if total_count == 0:
            return 0
            
        logger.info(f"Found {total_count} products with images for vendor {vendor_id}")
        
        # Process in batches
        batch_size = 10
        indexed_count = 0
        errors = 0
        
        # Added debug info
        print(f"Starting to index {total_count} products for vendor {vendor_id}")
        
        for i in range(0, total_count, batch_size):
            batch = products[i:i+batch_size]
            print(f"Processing batch {i//batch_size + 1} of {(total_count + batch_size - 1) // batch_size}")
            
            for product in batch:
                try:
                    # Debug print for category before processing
                    print(f"Processing product {product.id}: {product.name}")
                    
                    # Check if product has images
                    if not product.product_images.exists():
                        print(f"  Skipping product {product.id}: No images")
                        continue
                    
                    # Get the main image
                    main_image = product.product_images.first()
                    image_path = main_image.image.path
                    
                    # Check if image exists
                    if not os.path.exists(image_path):
                        print(f"  Skipping product {product.id}: Image file not found")
                        continue
                    
                    # Load and process the image
                    image = Image.open(image_path).convert('RGB')
                    
                    # Get product text for text embedding
                    product_text = f"{product.name} {product.description or ''} {self.get_category_name(product)}"
                    
                    # Generate embeddings
                    image_embedding = self.encode_image(image)
                    text_embedding = self.encode_text(product_text)
                    
                    # Combine embeddings (average)
                    combined_embedding = (image_embedding + text_embedding) / 2
                    
                    # Create unique vector ID
                    vector_id = f"clip_v{product.vendor.id}_p{product.id}"
                    
                    # Prepare metadata
                    metadata = {
                        "product_id": product.id,
                        "vendor_id": product.vendor.id,
                        "name": product.name,
                        "description": product.description or "",
                        "category": self.get_category_name(product),
                        "price": float(product.price),
                        "last_updated": datetime.now().isoformat()
                    }
                    
                    # Debug print before upserting
                    print(f"  Upserting vector for product {product.id}")
                    
                    # Upsert vector to Pinecone
                    self.index.upsert(
                        vectors=[
                            {
                                "id": vector_id,
                                "values": combined_embedding.tolist(),
                                "metadata": metadata
                            }
                        ]
                    )
                    
                    indexed_count += 1
                    print(f"  Successfully indexed product {product.id}")
                    
                except Exception as e:
                    errors += 1
                    logger.error(f"Error processing product {product.id}: {str(e)}")
                    print(f"  Error processing product {product.id}: {str(e)}")
        
        logger.info(f"Indexed {indexed_count} products, encountered {errors} errors")
        print(f"Indexing complete: {indexed_count} products indexed, {errors} errors")
        return indexed_count
        
    except Exception as e:
        logger.error(f"Error in index_vendor_products: {str(e)}")
        print(f"Error in index_vendor_products: {str(e)}")
        return 0
    
    
    
@require_http_methods(["GET"])
def similar_products_api(request, subdomain, product_id):
    """API endpoint for fetching similar products"""
    try:
        # Get product and vendor
        product = get_object_or_404(Product, id=product_id)
        
        # Set threshold - explicitly define it
        threshold = 60.0
        
        # Get similar products with threshold
        similar_products = get_similar_products_for_product(product, max_items=8, threshold=threshold)
        
        # Get product category name safely
        category_name = "Uncategorized"
        if hasattr(product, 'category') and product.category:
            if hasattr(product.category, 'category_name'):
                category_name = product.category.category_name
        
        # If no products above threshold, return empty but with metadata
        if not similar_products:
            return JsonResponse({
                'status': 'success',
                'similar_products': [],
                'threshold': threshold,  # Include threshold even with empty results
                'product_category': category_name
            })
        
        # Prepare product data
        products_data = []
        for p in similar_products:
            # Get category name safely
            p_category = "Uncategorized"
            if hasattr(p, 'category') and p.category:
                if hasattr(p.category, 'category_name'):
                    p_category = p.category.category_name
            
            # Check if products are in same category
            same_category = False
            if (hasattr(p, 'category') and p.category and 
                hasattr(product, 'category') and product.category):
                same_category = (p.category.id == product.category.id)
            
            # Ensure similarity score is always a number
            similarity_score = getattr(p, 'similarity_score', 60.0)
            if similarity_score is None or not isinstance(similarity_score, (int, float)):
                similarity_score = 60.0
            
            products_data.append({
                'id': p.id,
                'name': p.name,
                'price': float(p.price),
                'url': reverse('products:product_detail', kwargs={
                    'subdomain': subdomain,
                    'slug': p.slug
                }),
                'image_url': p.product_images.first().image.url if p.product_images.exists() else None,
                'similarity_score': float(similarity_score),  # Ensure it's a float
                'category': p_category,
                'same_category': same_category
            })
        
        # Return complete response with threshold and category
        return JsonResponse({
            'status': 'success',
            'similar_products': products_data,
            'threshold': threshold,
            'product_category': category_name
        })
    except Exception as e:
        print(f"Error in similar_products_api: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })
        
        
def get_similar_products_for_product(product, max_items=6, threshold=60.0):
    """Get similar products for product detail page"""
    try:
        recommender = ContentBasedRecommender()
        return recommender.get_similar_products(
            product, 
            max_items=max_items,
            threshold=threshold  # Pass threshold parameter
        )
    except Exception as e:
        logger.error(f"Error getting similar products: {str(e)}")
        # Fallback to category-based recommendations
        return Product.objects.filter(
            category=product.category, 
            vendor=product.vendor
        ).exclude(
            id=product.id
        ).order_by('-created_at')[:max_items]
        
from .models import Product, Category, Cart, Wishlist, ColorVariant, OrderItem

def product_list(request, subdomain):
    try:
        subdomain = subdomain.replace('.platform', '')
        subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
        vendor = subdomain_obj.vendor
        
        # Get customer from session if available
        customer = None
        if request.session.get('customer_id'):
            try:
                customer = Customer.objects.get(
                    id=request.session['customer_id'],
                    vendor=vendor
                )
            except Customer.DoesNotExist:
                pass
        
        # Get filter parameters
        category_id = request.GET.get('category')
        collection = request.GET.get('collection')
        sort_by = request.GET.get('sort', 'newest')
        
        # Start with all products for this vendor
        products = Product.objects.filter(vendor=vendor)
        
        # Apply category filter if specified
        selected_category_name = None
        if category_id:
            try:
                category = Category.objects.get(id=category_id, vendor=vendor)
                products = products.filter(category=category)
                selected_category_name = category.category_name
            except Category.DoesNotExist:
                pass
        
        # Apply collection filter if specified
        collection_name = None
        if collection:
            # Print for debugging
            print(f"Filtering by collection: {collection}")
            
            if collection == 'new_arrivals':
                # Get products from the last 30 days
                thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
                products = products.filter(created_at__gte=thirty_days_ago)
                collection_name = "New Arrivals"
            
            elif collection == 'best_sellers':
                print("Processing best_sellers collection")
                try:
                    # Simpler approach: Get products with any orders, sorted by order count
                    from django.db.models import Count
                    
                    # Direct query - get products with order counts
                    products = Product.objects.filter(vendor=vendor).annotate(
                        order_count=Count('orderitem')
                    ).filter(order_count__gt=0).order_by('-order_count')
                    
                    # If no results, try without filtering on order_count > 0
                    if not products.exists():
                        print("No products with orders found, showing all products with order counts")
                        products = Product.objects.filter(vendor=vendor).annotate(
                            order_count=Count('orderitem')
                        ).order_by('-order_count')
                    
                    # If still no results, use recent products as fallback
                    if not products.exists():
                        print("No order data found, using recently added products")
                        products = Product.objects.filter(vendor=vendor).order_by('-created_at')
                        
                    print(f"Found {products.count()} products for best sellers")
                    collection_name = "Best Sellers"
                except Exception as e:
                    print(f"Error processing best sellers: {str(e)}")
                    # Fall back to recent products
                    products = Product.objects.filter(vendor=vendor).order_by('-created_at')
                    collection_name = "Best Sellers"
            
            elif collection == 'season_special':
                # Get products with a discount/special offer
                discounted = products.filter(cut_price__isnull=False)
                if discounted.exists():
                    products = discounted
                collection_name = "Season Special"
        
        # Apply sorting (skip for best_sellers as it has its own sort)
        if collection != 'best_sellers':
            if sort_by == 'price_low':
                products = products.order_by('price')
            elif sort_by == 'price_high':
                products = products.order_by('-price')
            elif sort_by == 'newest':
                products = products.order_by('-created_at')
        
        # Always limit to a reasonable number to prevent performance issues
        if products.count() > 100:
            products = products[:100]
        
        context = {
            'vendor': vendor,
            'products': products,
            'customer': customer,
            'categories': Category.objects.filter(vendor=vendor),
            'selected_category_id': category_id,
            'selected_category_name': selected_category_name,
            'collection': collection,
            'collection_name': collection_name,
            'sort_by': sort_by,
            'wishlisted_products': list(Wishlist.objects.filter(
                customer_id=request.session.get('customer_id', None)
            ).values_list('product_id', flat=True)) if request.session.get('customer_id') else []
        }
        
        return render(request, 'products/product_list.html', context)
        
    except Exception as e:
        print(f"Error in product_list: {str(e)}")
        # Include traceback for better debugging
        import traceback
        print(traceback.format_exc())
        messages.error(request, "An error occurred while loading the page")
        return redirect('products:vendor_home', subdomain=subdomain)
        
        
        
