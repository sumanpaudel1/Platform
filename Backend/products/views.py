from django.shortcuts import render, get_object_or_404, redirect
from .forms import ProductForm
from django.contrib.auth.decorators import login_required
from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import Subdomain
from .models import Product, Category
from accounts.models import Vendor,VendorSetting ,Subdomain
from datetime import datetime



from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
from accounts.models import Vendor
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
    
    print(f"Rendering home page for subdomain: {subdomain}")
    print(f"User: {request.user}, is_authenticated: {request.user.is_authenticated}")
    # Get all products and new arrivals
    products = Product.objects.filter(vendor=vendor)
    
    new_arrivals = products.order_by('-created_at')[:8]  # Get 8 newest products
    
    # Filter by category if provided
    category_slug = request.GET.get('category')
    if category_slug:
        products = products.filter(category__slug=category_slug)
    
    
    context = {
        'vendor': vendor,
        'products': products,
        'new_arrivals': new_arrivals,
        'categories': Category.objects.filter(vendor=vendor),
        'cover_photos': vendor.settings.cover_photos.all().order_by('order'),
        'year': datetime.now().year,
        'show_popup': vendor.settings.show_popup,
        'popup_delay': vendor.settings.popup_delay
    }
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