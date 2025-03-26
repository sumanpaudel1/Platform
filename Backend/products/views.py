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
        
        # Debug prints
        # print("Debug Info:")
        # print(f"Session Data: {dict(request.session)}")
        # print(f"User Auth: {request.user.is_authenticated}")
        # print(f"Customer ID in session: {request.session.get('customer_id')}")
        
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
        #     print(f"Instagram posts found: {len(instagram_posts)}")
        #     print(f"First post: {instagram_posts[0] if instagram_posts else 'None'}")
            
        # print(f"Session customer_id: {request.session.get('customer_id')}")
        # print(f"Customer in context: {context['customer']}")
        # print(f"Context customer before render: {context['customer']}")
        
        return render(request, 'products/vendor_home.html', context)
        
    except Exception as e:
        # print(f"Error in vendor_home: {str(e)}")
        logger.error(f"Error in vendor_home: {str(e)}")
        messages.error(request, "An error occurred while loading the page")
        return redirect('accounts:customer_login' , subdomain=subdomain)




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






    

from django.http import JsonResponse
import json
from django.template.loader import render_to_string
import io

from django.views.decorators.http import require_http_methods

# @require_http_methods(["POST"])
# def add_to_cart(request):
#     try:
#         data = json.loads(request.body)
#         customer_id = request.session.get('customer_id')
        
#         if not customer_id:
#             return JsonResponse({
#                 'status': 'error',
#                 'message': 'Please login to continue'
#             }, status=401)
        
#         # Get product
#         product = get_object_or_404(Product, id=data.get('product_id'))
        
#         # Get or create cart item
#         cart_item, created = Cart.objects.get_or_create(
#             customer_id=customer_id,
#             product=product,
#             vendor=product.vendor,
#             defaults={
#                 'quantity': int(data.get('quantity', 1)),
#                 'color_id': data.get('color_id'),
#                 'size_id': data.get('size_id')
#             }
#         )
        
#         if not created:
#             cart_item.quantity += int(data.get('quantity', 1))
#             cart_item.save()
            
#         # Get updated cart count
#         cart_count = Cart.objects.filter(customer_id=customer_id).count()
        
#         return JsonResponse({
#             'status': 'success',
#             'message': 'Added to cart successfully',
#             'cart_count': cart_count
#         })
        
#     except Exception as e:
#         return JsonResponse({
#             'status': 'error',
#             'message': 'An error occurred while adding to cart'
#         }, status=500)



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

# def add_to_wishlist(request):
#     if not request.session.get('customer_id'):
#         return JsonResponse({
#             'status': 'error',
#             'message': 'Please login first'
#         }, status=401)

#     if request.method == 'POST':
#         data = json.loads(request.body)
#         product_id = data.get('product_id')
        
#         try:
#             customer = get_object_or_404(Customer, id=request.session['customer_id'])
#             product = get_object_or_404(Product, id=product_id)
            
#             wishlist_item, created = Wishlist.objects.get_or_create(
#                 customer=customer,
#                 product=product,
#                 vendor=product.vendor
#             )
            
#             wishlist_count = Wishlist.objects.filter(customer=customer).count()
            
#             return JsonResponse({
#                 'status': 'success',
#                 'wishlist_count': wishlist_count,
#                 'message': 'Added to wishlist' if created else 'Already in wishlist'
#             })
            
#         except Exception as e:
#             return JsonResponse({
#                 'status': 'error',
#                 'message': str(e)
#             }, status=400)
    
#     return JsonResponse({'status': 'error'}, status=400)



# def remove_from_wishlist(request, product_id):
#     if not request.session.get('customer_id'):
#         return JsonResponse({
#             'status': 'error',
#             'message': 'Please login first'
#         }, status=401)
        
#     if request.method == 'POST':
#         try:
#             customer = Customer.objects.get(id=request.session['customer_id'])
#             wishlist_item = Wishlist.objects.get(
#                 customer=customer,
#                 product_id=product_id
#             )
#             wishlist_item.delete()
            
#             # Get updated wishlist count
#             wishlist_count = Wishlist.objects.filter(customer=customer).count()
            
#             return JsonResponse({
#                 'status': 'success',
#                 'wishlist_count': wishlist_count,
#                 'message': 'Item removed from wishlist'
#             })
            
#         except (Customer.DoesNotExist, Wishlist.DoesNotExist) as e:
#             return JsonResponse({
#                 'status': 'error',
#                 'message': str(e)
#             }, status=404)
            
#     return JsonResponse({
#         'status': 'error',
#         'message': 'Invalid request method'
#     }, status=400)



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
        
        if status == 'COMPLETE':
            try:
                # Get order by transaction UUID
                order = Order.objects.get(order_id=transaction_uuid)
                vendor = order.vendor
                subdomain = vendor.subdomain
                
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
                
                # NOW create the notification since payment is confirmed
                create_order_notification(request, order)
                
                # For cart orders, delete the cart items now that payment is complete
                if not request.session.get('buy_now_data'):
                    Cart.objects.filter(customer=order.customer, vendor=order.vendor).delete()
                
                messages.success(request, "Payment successful!")
                return redirect(
                    f'/{subdomain}.platform/order/confirmation/{order.order_id}/'
                )
                
            except Order.DoesNotExist:
                messages.error(request, "Order not found")
                return redirect('products:vendor_home', subdomain=request.subdomain)
                
        else:
            messages.error(request, "Payment was not completed")
            return redirect('products:vendor_home', subdomain=request.subdomain)
            
    except Exception as e:
        logger.error(f"eSewa payment error: {str(e)}")
        messages.error(request, "An error occurred processing the payment")
        return redirect('products:vendor_home', subdomain=request.subdomain)
    
    

@csrf_exempt
def esewa_payment_failure(request):
    # Get the pending order ID from session
    if order_id := request.session.get('pending_esewa_order_id'):
        try:
            # Find the order
            order = Order.objects.get(order_id=order_id)
            
            # Change status to payment failed
            order.status = 'payment_failed'
            order.save()
            
            # Clear the pending order from session
            del request.session['pending_esewa_order_id']
            request.session.modified = True
            
            messages.error(request, "Payment failed or was cancelled")
        except Order.DoesNotExist:
            pass
    
    return redirect('products:vendor_home', subdomain=request.subdomain)



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
    subdomain = subdomain.replace('.platform', '')
    subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
    vendor = subdomain_obj.vendor
    
    query = request.GET.get('q', '')
    selected_categories = request.GET.get('categories', '').split(',')
    selected_categories = [cat for cat in selected_categories if cat.strip()]
    price_max = request.GET.get('price')
    sort = request.GET.get('sort', 'relevance')
    
    # Base queryset
    products = Product.objects.filter(vendor=vendor)
    
    # Apply search query
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) 
        ).distinct()
    
    # Apply category filter
    if selected_categories:
        category_ids = [int(cat) for cat in selected_categories]
        products = products.filter(category__id__in=category_ids)
    
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
    
    # Get max price for filter
    max_price = Product.objects.filter(vendor=vendor).order_by('-price').first()
    max_price = max_price.price if max_price else 1000
    
    
    if request.GET.get('type') == 'image':
        # Get search results from session
        search_results = request.session.get('image_search_results', [])
        
        if search_results:
            # Get product IDs from search results
            product_ids = [int(float(item['product_id'])) for item in search_results if 'product_id' in item]
            
            # Get products in order of search results
            products = []
            product_dict = {p.id: p for p in Product.objects.filter(id__in=product_ids, vendor=vendor)}
            
            # Preserve search order and attach similarity scores
            for result in search_results:
                if 'product_id' in result:
                    product_id = int(float(result['product_id']))
                    if product_id in product_dict:
                        product = product_dict[product_id]
                        product.similarity_score = float(result.get('similarity_score', 0))
                        product.explanation = result.get('explanation', f"Similarity: {product.similarity_score:.1f}%")
                        # Only add products with similarity scores above the threshold
                        products.append(product)
            
            # If no products above threshold
            if not products:
                messages.info(request, "No products matched your image with sufficient similarity. Try another image.")
            
    
    context = {
        'products': products,
        'query': query,
        'categories': Category.objects.filter(vendor=vendor),
        'selected_categories': selected_categories,
        'max_price': max_price,
        'selected_price': price_max,
        'sort': sort,
        'vendor': vendor,
        'is_image_search': request.GET.get('type') == 'image'
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
try:
    vector_db = VectorDatabase()
    clip_search = CLIPPineconeSearch()
except Exception as e:
    logger.error(f"Error initializing search engines: {str(e)}")
    vector_db = None
    clip_search = None


try:
    recommender_system = ContentBasedRecommender()
except Exception as e:
    logger.error(f"Failed to initialize recommendation system: {str(e)}")
    recommender_system = None
    

@require_http_methods(["POST"])
def image_search_view(request, subdomain):
    """View for processing image search"""
    try:
        if 'image_query' not in request.FILES:
            return JsonResponse({
                'status': 'error', 
                'message': 'No image file provided'
            })
            
        # Get vendor from subdomain
        subdomain = subdomain.replace('.platform', '')
        subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
        vendor = subdomain_obj.vendor
        
        # Process query image
        image_file = request.FILES['image_query']
        img = Image.open(io.BytesIO(image_file.read())).convert('RGB')
        
        print(f"Processing image search for vendor {vendor.id}")
        
        search_results = []
        
        # Set threshold to 60% for high relevance
        threshold = 60.0
        
        # Try CLIP search
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
            'redirect_url': reverse('products:search', kwargs={'subdomain': subdomain}) + '?type=image',
            'result_count': len(search_results)
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
    
    
    
    


# def debug_pinecone(request, subdomain):
#     """Debug view to see what's in Pinecone"""
#     try:
#         from ai_features.clip_pineconesearch import CLIPPineconeSearch
        
#         # Initialize search
#         clip_search = CLIPPineconeSearch()
        
#         if not clip_search or not clip_search.index:
#             return JsonResponse({'status': 'error', 'message': 'Pinecone not initialized'})
            
#         # Check Pinecone stats - CONVERT TO DICT for JSON serialization
#         stats = clip_search.index.describe_index_stats()
        
#         # Convert stats to a serializable dict
#         serializable_stats = {
#             'namespaces': stats.namespaces,
#             'dimension': stats.dimension,
#             'index_fullness': stats.index_fullness,
#             'total_vector_count': stats.total_vector_count,
#         }
        
#         # Get a few vectors as samples
#         try:
#             query_response = clip_search.index.query(
#                 vector=[0.0] * 512,  # Dummy vector
#                 top_k=5,
#                 include_metadata=True
#             )
#             matches = query_response.get('matches', [])
#         except Exception as e:
#             matches = str(e)
            
#         # Convert matches to serializable format if needed
#         serializable_matches = []
#         if isinstance(matches, list):
#             for match in matches:
#                 if hasattr(match, '__dict__'):
#                     serializable_matches.append(match.__dict__)
#                 else:
#                     serializable_matches.append(str(match))
        
#         return JsonResponse({
#             'status': 'success',
#             'stats': serializable_stats,
#             'index_name': getattr(stats, 'index_name', '(unknown)'),
#             'sample_vectors': serializable_matches
#         })
            
#     except Exception as e:
#         import traceback
#         return JsonResponse({
#             'status': 'error', 
#             'message': str(e),
#             'traceback': traceback.format_exc()
#         })
        
        
        
# from django.http import JsonResponse

# def debug_category(request, subdomain):
#     """Debug view to examine the Category structure"""
#     from products.models import Product, Category
#     import inspect
    
#     # Get a product with category
#     products = Product.objects.filter(category__isnull=False)
#     if not products.exists():
#         return JsonResponse({"error": "No products with categories found"})
    
#     product = products.first()
#     category = product.category
    
#     # Analyze category
#     category_info = {
#         "product_id": product.id,
#         "product_name": product.name,
#         "category_id": category.id if hasattr(category, 'id') else None,
#         "category_type": str(type(category)),
#         "dir": dir(category),
#         "attributes": {},
#     }
    
#     # Check common attribute names
#     for attr in ["name", "category_name", "title", "label", "category", "value"]:
#         try:
#             category_info["attributes"][attr] = str(getattr(category, attr, "Not found"))
#         except Exception as e:
#             category_info["attributes"][attr] = f"Error: {str(e)}"
    
#     # Try to get string representation
#     try:
#         category_info["string_representation"] = str(category)
#     except Exception as e:
#         category_info["string_representation"] = f"Error: {str(e)}"
    
#     return JsonResponse(category_info)



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