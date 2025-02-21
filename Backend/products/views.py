from django.shortcuts import render, get_object_or_404, redirect
from .forms import ProductForm
from django.contrib.auth.decorators import login_required
from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import Subdomain
from .models import Product, Category, Cart, Wishlist
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





@vendor_login_required
def vendor_home(request, subdomain):
    subdomain = subdomain.replace('.platform', '')
    subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
    vendor = subdomain_obj.vendor
    
    customer = request.customer
    
    # Add debug prints
    print("Debug Info:")
    print(f"Session Data: {dict(request.session)}")
    print(f"User Auth: {request.user.is_authenticated}")
    print(f"Customer ID in session: {request.session.get('customer_id')}")
    
    
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
    
    # Filter by category if provided
    category_slug = request.GET.get('category')
    if category_slug:
        products = products.filter(category__slug=category_slug)
        
        
    wishlisted_products = []
    if request.session.get('customer_id'):
        wishlisted_products = Wishlist.objects.filter(
            customer_id=request.session['customer_id']
        ).values_list('product_id', flat=True)
    
    context = {
        'vendor': vendor,
        'products': products,
        'customer': customer,
        'new_arrivals': new_arrivals,
        'categories': Category.objects.filter(vendor=vendor),
        'cover_photos': vendor.settings.cover_photos.all().order_by('order'),
        'year': datetime.now().year,
        'show_popup': vendor.settings.show_popup,
        'popup_delay': vendor.settings.popup_delay,
        'debug': settings.DEBUG,
        'wishlisted_products': list(wishlisted_products),
    }
    
    print(f"Session customer_id: {request.session.get('customer_id')}")  # Debug print
    print(f"Customer in context: {context['customer']}")  # Debug print
    print(f"Context customer before render: {context['customer']}")  # Debug print
    return render(request, 'products/vendor_home.html', context)



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
    
    related_products = Product.objects.filter(
        category=product.category
    ).exclude(id=product.id)[:4]
    
    context = {
        'vendor': vendor,
        'product': product,
        'related_products': related_products
    }
    return render(request, 'products/product_detail.html', context)

@login_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.vendor = request.user
            product.save()
            return redirect('product_list')
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

from django.views.decorators.http import require_http_methods

@require_http_methods(["POST"])
def add_to_cart(request):
    try:
        data = json.loads(request.body)
        customer_id = request.session.get('customer_id')
        
        if not customer_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Please login to continue'
            }, status=401)
        
        # Get product
        product = get_object_or_404(Product, id=data.get('product_id'))
        
        # Get or create cart item
        cart_item, created = Cart.objects.get_or_create(
            customer_id=customer_id,
            product=product,
            vendor=product.vendor,
            defaults={
                'quantity': int(data.get('quantity', 1)),
                'color_id': data.get('color_id'),
                'size_id': data.get('size_id')
            }
        )
        
        if not created:
            cart_item.quantity += int(data.get('quantity', 1))
            cart_item.save()
            
        # Get updated cart count
        cart_count = Cart.objects.filter(customer_id=customer_id).count()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Added to cart successfully',
            'cart_count': cart_count
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': 'An error occurred while adding to cart'
        }, status=500)



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


def update_cart(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        item_id = data.get('item_id')
        action = data.get('action')
        
        try:
            cart_item = Cart.objects.get(id=item_id)
            
            if action == 'increase':
                cart_item.quantity += 1
            elif action == 'decrease':
                if cart_item.quantity > 1:
                    cart_item.quantity -= 1
                else:
                    cart_item.delete()
                    cart_items = Cart.objects.filter(customer=cart_item.customer)
                    subtotal = sum(item.total_price for item in cart_items)
                    return JsonResponse({
                        'status': 'success',
                        'quantity': 0,
                        'cart_count': cart_items.count(),
                        'subtotal': float(subtotal),
                        'total': float(subtotal)
                    })
            
            cart_item.save()
            
            # Recalculate totals
            cart_items = Cart.objects.filter(customer=cart_item.customer)
            subtotal = sum(item.total_price for item in cart_items)
            
            return JsonResponse({
                'status': 'success',
                'quantity': cart_item.quantity,
                'item_total': float(cart_item.total_price),
                'cart_count': cart_items.count(),
                'subtotal': float(subtotal),
                'total': float(subtotal)  # Add shipping if needed
            })
            
        except Cart.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Cart item not found'
            }, status=404)
    
    return JsonResponse({'status': 'error'}, status=400)


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

def add_to_wishlist(request):
    if not request.session.get('customer_id'):
        return JsonResponse({
            'status': 'error',
            'message': 'Please login first'
        }, status=401)

    if request.method == 'POST':
        data = json.loads(request.body)
        product_id = data.get('product_id')
        
        try:
            customer = get_object_or_404(Customer, id=request.session['customer_id'])
            product = get_object_or_404(Product, id=product_id)
            
            wishlist_item, created = Wishlist.objects.get_or_create(
                customer=customer,
                product=product,
                vendor=product.vendor
            )
            
            wishlist_count = Wishlist.objects.filter(customer=customer).count()
            
            return JsonResponse({
                'status': 'success',
                'wishlist_count': wishlist_count,
                'message': 'Added to wishlist' if created else 'Already in wishlist'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'status': 'error'}, status=400)



def remove_from_wishlist(request, product_id):
    if not request.session.get('customer_id'):
        return JsonResponse({
            'status': 'error',
            'message': 'Please login first'
        }, status=401)
        
    if request.method == 'POST':
        try:
            customer = Customer.objects.get(id=request.session['customer_id'])
            wishlist_item = Wishlist.objects.get(
                customer=customer,
                product_id=product_id
            )
            wishlist_item.delete()
            
            # Get updated wishlist count
            wishlist_count = Wishlist.objects.filter(customer=customer).count()
            
            return JsonResponse({
                'status': 'success',
                'wishlist_count': wishlist_count,
                'message': 'Item removed from wishlist'
            })
            
        except (Customer.DoesNotExist, Wishlist.DoesNotExist) as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=404)
            
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=400)



from django.http import JsonResponse
import json

def toggle_wishlist(request):
    if not request.session.get('customer_id'):
        return JsonResponse({
            'status': 'error',
            'message': 'Please login first'
        }, status=401)

    if request.method == 'POST':
        data = json.loads(request.body)
        product_id = data.get('product_id')
        
        try:
            customer = Customer.objects.get(id=request.session['customer_id'])
            product = Product.objects.get(id=product_id)
            
            # Check if item exists in wishlist
            wishlist_item = Wishlist.objects.filter(
                customer=customer,
                product=product
            ).first()
            
            if wishlist_item:
                # Remove from wishlist
                wishlist_item.delete()
                message = 'Removed from wishlist'
            else:
                # Add to wishlist
                Wishlist.objects.create(
                    customer=customer,
                    product=product,
                    vendor=product.vendor
                )
                message = 'Added to wishlist'
            
            # Get updated wishlist count
            wishlist_count = Wishlist.objects.filter(customer=customer).count()
            
            return JsonResponse({
                'status': 'success',
                'wishlist_count': wishlist_count,
                'message': message
            })
            
        except (Customer.DoesNotExist, Product.DoesNotExist) as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'status': 'error'}, status=400)










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

            # Get cart items
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

            # Create order
            order = Order.objects.create(
                customer_id=customer_id,
                vendor=vendor,
                delivery_address=delivery_address,
                payment_method=payment_method,
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

            # Clear cart
            cart_items.delete()
            
            create_order_notification(request, order)


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
                
            elif data['payment_method'] == 'esewa':
                    esewa = EsewaPayment()
                    payment_url, params = esewa.generate_payment_data(order)  # Changed from generate_payment_url
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
            'message': 'An error occurred while placing your order'
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
        order = Order.objects.get(order_id=order_id)
        esewa = EsewaPayment()
        payment_url, params = esewa.generate_payment_data(order)  # Changed from generate_payment_url
        
        # Store payment attempt
        Payment.objects.create(
            order=order,
            payment_method='esewa',
            amount=order.total_amount,
            status='pending'
        )
        
        context = {
            'payment_url': payment_url,
            'params': params
        }
        
        return render(request, 'products/esewa_redirect.html', context)
        
    except Order.DoesNotExist:
        messages.error(request, "Order not found")
        return redirect('products:cart', subdomain=request.subdomain)



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
                order.status = 'processing'
                order.save()
                
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
    messages.error(request, "Payment failed or was cancelled")
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
        ).order_by('-created_at').prefetch_related('items', 'items__product', 'items__product__product_images')
        
        context = {
            'orders': orders,
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


def delete_order(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    try:
        customer_id = request.session.get('customer_id')
        if not customer_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Please login to continue'
            }, status=401)
        
        order = get_object_or_404(Order, 
            order_id=order_id, 
            customer_id=customer_id,
            status='cancelled'
        )
        
        order.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Order deleted successfully'
        })
        
    except Order.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Order not found'
        })
    except Exception as e:
        logger.error(f"Delete order error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'An error occurred while deleting the order'
        })
        
  
        

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



