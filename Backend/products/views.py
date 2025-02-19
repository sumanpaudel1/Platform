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

def add_to_cart(request):
    if not request.session.get('customer_id'):
        return JsonResponse({
            'status': 'error',
            'message': 'Please login first'
        }, status=401)

    if request.method == 'POST':
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)
        
        try:
            customer = Customer.objects.get(id=request.session['customer_id'])
            product = Product.objects.get(id=product_id)
            
            cart_item, created = Cart.objects.get_or_create(
                customer=customer,
                product=product,
                vendor=product.vendor,
                defaults={'quantity': quantity}
            )
            
            if not created:
                cart_item.quantity += int(quantity)
                cart_item.save()
            
            # Get updated cart count
            cart_count = Cart.objects.filter(customer=customer).count()
            
            return JsonResponse({
                'status': 'success',
                'cart_count': cart_count,
                'message': 'Added to cart successfully'
            })
            
        except (Customer.DoesNotExist, Product.DoesNotExist):
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid request'
            }, status=400)
            
    return JsonResponse({'status': 'error'}, status=400)




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






