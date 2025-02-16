from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from .forms import RegistrationForm, LoginForm, VendorProfileForm, VendorSettingForm
from .models import Vendor, OTP, VendorProfile, StorePhoto, VendorSetting, CoverPhoto, Subdomain
from .utils import generate_otp, send_otp_to_email

def register(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            vendor = form.save(commit=False)
            vendor.set_password(form.cleaned_data['password1'])
            vendor.is_verified = False
            vendor.save()

            otp = generate_otp()
            send_otp_to_email(vendor.email, otp)
            OTP.objects.create(email=vendor.email, otp=otp)

            return redirect('verify_otp', email=vendor.email)
    else:
        form = RegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})

def verify_otp(request, email):
    if request.method == "POST":
        otp_digits = [request.POST.get(f'otp{i}', '') for i in range(1, 7)]
        entered_otp = ''.join(otp_digits)
        
        try:
            otp_entry = OTP.objects.filter(
                email=email,
                status='active'
            ).latest('created_at')
            
            if otp_entry.is_valid(entered_otp):
                otp_entry.mark_as_used()
                vendor = Vendor.objects.get(email=email)
                vendor.is_verified = True
                vendor.save()
                messages.success(request, "Email verified successfully!")
                return redirect('login')
            else:
                error_message = "OTP has expired. Please request a new one." if otp_entry.is_expired() else "Invalid OTP. Please try again."
                return render(request, 'accounts/otp_verification.html', {
                    'email': email,
                    'error': error_message,
                    'preserve_timer': True
                })
            
        except OTP.DoesNotExist:
            return render(request, 'accounts/otp_verification.html', {
                'email': email,
                'error': "No active OTP found. Please request a new one.",
                'preserve_timer': True
            })
    
    return render(request, 'accounts/otp_verification.html', {
        'email': email,
        'preserve_timer': False
    })

def login_vendor(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            
            try:
                vendor = Vendor.objects.get(email=email)
                vendor = authenticate(request, username=email, password=password)
                
                if vendor is not None:
                    if vendor.is_verified:
                        login(request, vendor)
                        return redirect('home')
                    else:
                        return render(request, 'accounts/login.html', 
                                    {'form': form, 'error': "Please verify your email first"})
                else:
                    return render(request, 'accounts/login.html', 
                                {'form': form, 'error': "Invalid email or password"})
            except Vendor.DoesNotExist:
                return render(request, 'accounts/login.html', 
                            {'form': form, 'error': "No account found with this email"})
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})

from django.contrib.auth.decorators import login_required

@login_required(login_url='login')
def home(request):
    return render(request, 'accounts/home.html')

from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_vendor(request):
    logout(request)
    return redirect('login')

from django.shortcuts import redirect
from django.contrib import messages
import logging
from .models import OTP
from .utils import generate_otp, send_otp_to_email

logger = logging.getLogger(__name__)

def resend_otp(request, email):
    if request.method == "POST":
        try:
            OTP.objects.filter(email=email, status='active').update(status='expired')
            new_otp = generate_otp()
            OTP.objects.create(email=email, otp=str(new_otp))
            email_sent = send_otp_to_email(email, new_otp)
            
            if email_sent:
                logger.info(f"OTP sent successfully to {email}")
                messages.success(request, "New OTP has been sent to your email")
            else:
                logger.error(f"Failed to send OTP to {email}")
                messages.error(request, "Failed to send OTP. Please try again")
                
        except Exception as e:
            logger.error(f"Error in resend_otp: {str(e)}")
            messages.error(request, "An error occurred. Please try again")
    
    return redirect('verify_otp', email=email)

def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get('email')
        try:
            vendor = Vendor.objects.get(email=email)
            otp = generate_otp()
            OTP.objects.filter(email=email).update(status='expired')
            OTP.objects.create(email=email, otp=str(otp), status='active')
            
            if send_otp_to_email(email, otp):
                messages.success(request, "Password reset OTP has been sent to your email")
                return redirect('verify_reset_otp', email=email)
            else:
                messages.error(request, "Failed to send OTP. Please try again")
                
        except Vendor.DoesNotExist:
            messages.error(request, "No account found with this email address")
            return redirect('forgot_password')
    
    return render(request, 'accounts/forgot_password.html')

def verify_reset_otp(request, email):
    if request.method == "POST":
        otp_digits = [request.POST.get(f'otp{i}', '') for i in range(1, 7)]
        entered_otp = ''.join(otp_digits)
        
        try:
            otp_entry = OTP.objects.filter(email=email, status='active').latest('created_at')
            
            if otp_entry.is_valid(entered_otp):
                otp_entry.mark_as_used()
                return redirect('reset_password', email=email)
            else:
                error_message = "OTP has expired. Please request a new one." if otp_entry.is_expired() else "Invalid OTP. Please try again."
                return render(request, 'accounts/otp_verification.html', {
                    'email': email,
                    'error': error_message,
                    'preserve_timer': True,
                    'is_password_reset': True
                })
                
        except OTP.DoesNotExist:
            return render(request, 'accounts/otp_verification.html', {
                'email': email,
                'error': "No active OTP found",
                'is_password_reset': True
            })
    
    return render(request, 'accounts/otp_verification.html', {
        'email': email,
        'is_password_reset': True
    })

def reset_password(request, email):
    if request.method == "POST":
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return render(request, 'accounts/reset_password.html', {'email': email})
            
        try:
            vendor = Vendor.objects.get(email=email)
            vendor.set_password(password1)
            vendor.save()
            messages.success(request, "Password reset successfully")
            return redirect('login')
            
        except Vendor.DoesNotExist:
            messages.error(request, "Vendor not found")
    
    return render(request, 'accounts/reset_password.html', {'email': email})



from django.shortcuts import render
from django.http import HttpResponse

def main_home(request):
    return HttpResponse('Welcome to the main homepage')




# accounts/views.py


from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
def vendor_profile(request):
    try:
        profile = request.user.profile
        store_photos = request.user.storephoto_set.all()  # Get store photos
        is_new = False
    except VendorProfile.DoesNotExist:
        profile = VendorProfile(vendor=request.user)
        store_photos = []
        is_new = True

    if request.method == "POST":
        form = VendorProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.vendor = request.user
            
            # Handle profile photo
            if 'profile_photo' in request.FILES:
                profile.profile_photo = request.FILES['profile_photo']
                
            # Handle store photos
            store_photos = request.FILES.getlist('store_photos')
            for photo in store_photos:
                StorePhoto.objects.create(
                    vendor=request.user,
                    image=photo
                )
                
            profile.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('vendor_profile')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = VendorProfileForm(instance=profile)

    return render(request, 'accounts/profile.html', {
        'form': form,
        'profile': profile,
        'is_new': is_new,
        'store_photos': store_photos
    })



from django.contrib.auth.decorators import login_required
from .models import VendorSetting

from django.contrib import messages
from django.shortcuts import render, redirect
from .models import VendorSetting, CoverPhoto
from django.contrib.auth.decorators import login_required

@login_required
def store_settings(request):
    # Get or create settings for vendor
    try:
        settings = VendorSetting.objects.get(vendor=request.user)
    except VendorSetting.DoesNotExist:
        settings = VendorSetting(vendor=request.user)
        settings.save()

    if request.method == 'POST':
        # Handle regular form fields
        settings.store_name = request.POST.get('store_name')
        settings.tagline = request.POST.get('tagline')
        settings.about = request.POST.get('about')
        settings.announcement = request.POST.get('announcement')
        
        # Handle colors and typography
        settings.primary_color = request.POST.get('primary_color')
        settings.secondary_color = request.POST.get('secondary_color')
        settings.accent_color = request.POST.get('accent_color')
        settings.heading_font = request.POST.get('heading_font')
        settings.body_font = request.POST.get('body_font')

        # Handle social links
        settings.facebook = request.POST.get('facebook')
        settings.instagram = request.POST.get('instagram')
        settings.twitter = request.POST.get('twitter')

        # Handle contact info
        settings.contact_email = request.POST.get('contact_email')
        settings.contact_phone = request.POST.get('contact_phone')
        settings.contact_address = request.POST.get('contact_address')

        # Handle SEO fields
        settings.meta_title = request.POST.get('meta_title')
        settings.meta_description = request.POST.get('meta_description')

        # Handle popup settings
        settings.popup_title = request.POST.get('popup_title')
        settings.popup_text = request.POST.get('popup_text')
        settings.show_popup = 'show_popup' in request.POST
        settings.popup_delay = request.POST.get('popup_delay')

        # Handle file uploads
        if request.FILES.get('logo'):
            settings.logo = request.FILES['logo']
        if request.FILES.get('favicon'):
            settings.favicon = request.FILES['favicon']
        if request.FILES.get('popup_image'):
            settings.popup_image = request.FILES['popup_image']

        # Handle multiple cover photos
        if request.FILES.getlist('cover_photos'):
            for photo in request.FILES.getlist('cover_photos'):
                CoverPhoto.objects.create(
                    vendor_setting=settings,
                    image=photo
                )

        try:
            settings.save()
            messages.success(request, 'Settings updated successfully!')
        except Exception as e:
            messages.error(request, f'Error saving settings: {str(e)}')
        
        return redirect('vendor_settings')

    context = {
        'settings': settings,
        'cover_photos': settings.cover_photos.all() if settings.id else []
    }
    return render(request, 'accounts/store_settings.html', context)
    
    
@login_required
def delete_cover_photo(request, photo_id):
    if request.method == 'POST':
        try:
            photo = CoverPhoto.objects.get(id=photo_id, vendor_setting__vendor=request.user)
            photo.delete()
            messages.success(request, 'Cover photo deleted successfully!')
        except CoverPhoto.DoesNotExist:
            messages.error(request, 'Cover photo not found!')
    return redirect('vendor_settings')



#Product views






# Remove duplicate imports and organize them at the top
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from products.models import Product, Category, ColorVariant, SizeVariant, ProductImage
from .forms import (
    ProductForm,  CategoryForm, ProductColorVariantForm, ProductSizeVariantForm 
)
from django.http import JsonResponse


@login_required
def vendor_products(request):
    """View for listing all products of a vendor"""
    products = Product.objects.filter(vendor=request.user).prefetch_related(
        'product_images',  # Use the new related_name
        'category'
    ).order_by('-created_at')
    
    context = {
        'products': products,
        'active_tab': 'products'
    }
    return render(request, 'accounts/vendor_products.html', context)

# Keep only these product-related views and update them

@login_required
def vendor_product_edit(request, pk):
    """View for editing a vendor's product"""
    product = get_object_or_404(Product, pk=pk, vendor=request.user)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save()
            
            

            
            # Handle product images
            if request.FILES.getlist('product_images'):
                for image in request.FILES.getlist('product_images'):
                    ProductImage.objects.create(product=product, image=image)

            # Handle color variants
            product.color_variant.set(request.POST.getlist('color_variants'))
            
            # Handle size variants
            product.size_variant.set(request.POST.getlist('size_variants'))

            messages.success(request, 'Product updated successfully!')
            return redirect('vendor_products')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ProductForm(instance=product)
    
    context = {
        'form': form,
        'product': product,
        'category_form': CategoryForm(),
        'color_form': ProductColorVariantForm(),
        'size_form': ProductSizeVariantForm(),
        'categories': Category.objects.all(),  # Add this line
        'images': product.product_images.all(),
        'colors': product.color_variant.all(),
        'sizes': product.size_variant.all(),
        'active_tab': 'category',
        'is_edit': True
    }
    return render(request, 'accounts/vendor_product_form.html', context)

@login_required
def delete_product_image(request, image_id):
    if request.method == 'POST':
        try:
            image = get_object_or_404(ProductImage, 
                                    id=image_id, 
                                    product__vendor=request.user)
            image.delete()
            return JsonResponse({
                'status': 'success',
                'message': 'Image deleted successfully!'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)





@login_required
def vendor_product_delete(request, pk):
    """View for deleting a vendor's product"""
    product = get_object_or_404(Product, pk=pk, vendor=request.user)
    
    if request.method == 'POST':
        try:
            # Delete associated images first
            product.productimage_set.all().delete()
            # Delete the product
            product.delete()
            messages.success(request, 'Product deleted successfully!')
        except Exception as e:
            messages.error(request, f'Error deleting product: {str(e)}')
        return redirect('vendor_products')
    
    # If GET request, show confirmation page
    context = {
        'product': product,
        'active_tab': 'products'
    }
    return render(request, 'accounts/vendor_product_delete.html', context)



@login_required
def add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)  # Add request.FILES
        if form.is_valid():
            try:
                category = form.save(commit=False)
                category.vendor = request.user
                
                # Handle category image
                if 'category_image' in request.FILES:
                    category.category_image = request.FILES['category_image']
                
                category.save()
                return JsonResponse({
                    'status': 'success',
                    'id': category.id,
                    'name': category.category_name,
                    'image_url': category.category_image.url if category.category_image else None
                })
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=400)
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid form data',
            'errors': form.errors
        }, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

from django.db import IntegrityError
from django.http import JsonResponse

@login_required
def add_color_variant(request):
    if request.method == 'POST':
        form = ProductColorVariantForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                color = form.save(commit=False)
                color.vendor = request.user
                if 'image' in request.FILES:
                    color.image = request.FILES['image']
                color.save()
                
                return JsonResponse({
                    'status': 'success',
                    'id': color.id,
                    'color_name': color.color_name,
                    'image_url': color.image.url if color.image else None
                })
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=400)
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid form data'
    }, status=400)

@login_required
def add_size_variant(request):
    if request.method == 'POST':
        form = ProductSizeVariantForm(request.POST)
        if form.is_valid():
            try:
                size = form.save(commit=False)
                size.vendor = request.user
                size.save()
                
                return JsonResponse({
                    'status': 'success',
                    'id': size.id,
                    'size_name': size.size_name,
                    'price': str(size.price)
                })
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=400)
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid form data'
    }, status=400)

@login_required
def vendor_product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.vendor = request.user
            product.save()
            
            images = request.FILES.getlist('product_images')
            for img in images:
                ProductImage.objects.create(product=product, image=img)

            # Handle new color variants
            new_colors = []
            for key in request.POST:
                if key.startswith('new_color_variants'):
                    index = key.split('[')[1].split(']')[0]
                    color_name = request.POST.get(f'new_color_variants[{index}][color_name]')
                    new_colors.append(ColorVariant(
                        product=product,
                        color_name=color_name,
                        vendor=request.user
                    ))
            ColorVariant.objects.bulk_create(new_colors)

            # Handle new size variants
            new_sizes = []
            for key in request.POST:
                if key.startswith('new_size_variants'):
                    index = key.split('[')[1].split(']')[0]
                    size_name = request.POST.get(f'new_size_variants[{index}][size_name]')
                    price = request.POST.get(f'new_size_variants[{index}][price]')
                    new_sizes.append(SizeVariant(
                        product=product,
                        size_name=size_name,
                        price=price,
                        vendor=request.user
                    ))
            SizeVariant.objects.bulk_create(new_sizes)

            # Handle existing variants
            product.color_variant.set(request.POST.getlist('color_variants'))
            product.size_variant.set(request.POST.getlist('size_variants'))

            # Handle deletions
            for color_id in request.POST.getlist('delete_colors'):
                ColorVariant.objects.filter(id=color_id, product=product).delete()
            for size_id in request.POST.getlist('delete_sizes'):
                SizeVariant.objects.filter(id=size_id, product=product).delete()

            messages.success(request, 'Product created successfully!')
            return redirect('vendor_products')
        else:
            print(form.errors)  # Debug
            messages.error(request, f"Form errors: {form.errors}")
    else:
        form = ProductForm()
    return render(request, 'accounts/vendor_product_form.html', {
        'form': form,
        'category_form': CategoryForm(),
        'color_form': ProductColorVariantForm(),
        'size_form': ProductSizeVariantForm(),
        'categories': Category.objects.filter(vendor=request.user),  # Add this line to get vendor's categories
        'active_tab': 'category',
        'active_tab': 'products',
    })
    
        
    

@login_required
def add_product_images(request, pk):
    if request.method == 'POST':
        product = get_object_or_404(Product, pk=pk, vendor=request.user)
        try:
            for image in request.FILES.getlist('product_images'):
                ProductImage.objects.create(
                    product=product,
                    image=image
                )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)





from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from products.models import Category, ColorVariant, SizeVariant, ProductImage

@login_required
def delete_category(request, pk):
    if request.method == 'POST':
        category = get_object_or_404(Category, pk=pk, vendor=request.user)
        category.delete()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@login_required
def delete_color_variant(request, pk):
    if request.method == 'POST':
        variant = get_object_or_404(ColorVariant, pk=pk, vendor=request.user)
        variant.delete()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@login_required
def delete_size_variant(request, pk):
    if request.method == 'POST':
        variant = get_object_or_404(SizeVariant, pk=pk, vendor=request.user)
        variant.delete()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})




from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from products.models import Product


@login_required
def delete_product(request, pk):
    if request.method == 'POST':
        try:
            product = get_object_or_404(Product, pk=pk, vendor=request.user)
            product.delete()
            return JsonResponse({'status': 'success'})
        except Product.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Product not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)
    
    
    
    
    
    
    
    
   
   
    
    
 # customer login register views

    
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate
from .forms import CustomerRegistrationForm, OTPVerificationForm
from .models import Customer, OTP
from .utils import generate_otp, send_otp_to_email
from .models import Vendor
from .models import Subdomain

from functools import wraps
from django.shortcuts import redirect
from django.urls import reverse
from .models import Vendor




def customer_register(request, subdomain):
    subdomain = subdomain.replace('.platform', '')
    subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
    vendor = subdomain_obj.vendor
    
    if request.method == "POST":
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            try:
                # Create customer but don't activate yet
                customer = form.save(commit=False)
                customer.vendor = vendor
                customer.is_active = False
                customer.set_password(form.cleaned_data['password1'])
                customer.save()

                # Generate and save new OTP
                otp_val = generate_otp()
                
                # Expire any existing OTPs
                OTP.objects.filter(email=customer.email).update(status='expired')
                
                # Create new OTP record
                otp_obj = OTP.objects.create(
                    email=customer.email,
                    otp=otp_val,
                    status='active'
                )
                
                # Store email in session for OTP verification
                request.session['pending_customer_email'] = customer.email
                
                # Send OTP email
                if send_otp_to_email(customer.email, otp_val):
                    messages.success(request, 
                        "Registration successful! Please check your email for verification code.")
                    return redirect('verify_customer_otp', subdomain=subdomain)
                else:
                    messages.error(request, 
                        "Failed to send verification code. Please try again or contact support.")
                    customer.delete()  # Roll back customer creation
                    
            except Exception as e:
                messages.error(request, f"Registration failed: {str(e)}")
                
    else:
        form = CustomerRegistrationForm()
    
    return render(request, 'accounts/customer_register.html', {
        'form': form,
        'vendor': vendor
    })



def verify_customer_otp(request, subdomain):
    subdomain = subdomain.replace('.platform', '')
    subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
    vendor = subdomain_obj.vendor
    
    pending_email = request.session.get('pending_customer_email')
    if not pending_email:
        messages.error(request, "No pending verification found.")
        return redirect('customer_register', subdomain=subdomain)

    if request.method == "POST":
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            otp_input = form.cleaned_data['otp']
            try:
                # Get the OTP object
                otp_obj = get_object_or_404(OTP, email=pending_email, status='active')
                
                if otp_obj.is_valid(otp_input):
                    # Get the customer specific to this vendor
                    customer = get_object_or_404(Customer, 
                                               email=pending_email,
                                               vendor=vendor,
                                               is_active=False)
                    
                    # Mark OTP as used and activate customer
                    otp_obj.mark_as_used()
                    customer.is_active = True
                    customer.save()
                    
                    # Log the customer in
                    login(request, customer, 
                          backend='django.contrib.auth.backends.ModelBackend')
                    
                    messages.success(request, 
                                   "Your account has been verified and you are now logged in.")
                    
                    # Clear session data
                    if 'pending_customer_email' in request.session:
                        del request.session['pending_customer_email']
                    
                    return redirect('products:vendor_home', subdomain=subdomain)
                else:
                    messages.error(request, "Invalid or expired OTP.")
            except OTP.DoesNotExist:
                messages.error(request, "OTP not found or expired.")
            except Customer.DoesNotExist:
                messages.error(request, "Customer account not found.")
            except Exception as e:
                messages.error(request, f"An error occurred: {str(e)}")
            
            return redirect('verify_customer_otp', subdomain=subdomain)
    else:
        form = OTPVerificationForm()

    return render(
        request,
        'accounts/customer_otp_verification.html',
        {
            'form': form,
            'email': pending_email,
            'vendor': vendor
        }
    )
    



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.urls import reverse
from .models import Customer, Subdomain



def vendor_login_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        subdomain = kwargs.get('subdomain', '').replace('.platform', '')
        
        print(f"Checking auth for subdomain: {subdomain}")
        print(f"User authenticated: {request.user.is_authenticated}")
        print(f"Session data: {dict(request.session)}")
        
        # Check session authentication first
        if not request.session.get('is_authenticated'):
            messages.error(request, "Please log in to continue.")
            return redirect(f'/{subdomain}.platform/customer/login/')
        
        try:
            subdomain_obj = Subdomain.objects.get(subdomain=subdomain)
            vendor = subdomain_obj.vendor
            
            # Get customer from session
            customer_id = request.session.get('customer_id')
            if customer_id:
                try:
                    customer = Customer.objects.get(
                        id=customer_id,
                        vendor=vendor,
                        is_active=True
                    )
                    request.customer = customer
                    return view_func(request, *args, **kwargs)
                except Customer.DoesNotExist:
                    pass
            
            # Clear invalid session
            request.session.flush()
            messages.error(request, "Please log in again.")
            return redirect(f'/{subdomain}.platform/customer/login/')
            
        except Subdomain.DoesNotExist:
            messages.error(request, "Invalid store subdomain.")
            return redirect(f'/{subdomain}.platform/customer/login/')
            
    return _wrapped_view



def customer_login(request, subdomain):
    sub = subdomain.replace('.platform', '')
    subdomain_obj = get_object_or_404(Subdomain, subdomain=sub)
    vendor = subdomain_obj.vendor

    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            customer = Customer.objects.get(email=email, vendor=vendor)
            
            if not customer.is_active:
                messages.error(request, "Account is not active.")
                return render(request, 'accounts/customer_login.html', {'vendor': vendor})
            
            if customer.check_password(password):
                # Important: Set the backend attribute before login
                customer.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, customer)
                
                # Set session data
                request.session['is_authenticated'] = True
                request.session['customer_id'] = customer.id
                request.session['vendor_id'] = vendor.id
                request.session['subdomain'] = sub
                request.session.save()  # Explicitly save session
                
                print(f"User authenticated: {request.user.is_authenticated}")
                print(f"Session data: {dict(request.session)}")
                
                # Use direct path for redirection
                target_url = f'/{sub}.platform/home/'
                print(f"Redirecting to: {target_url}")
                return redirect(target_url)
            else:
                messages.error(request, "Invalid password.")
                
        except Customer.DoesNotExist:
            messages.error(request, "No account found with this email for this store.")
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")

    return render(request, 'accounts/customer_login.html', {'vendor': vendor})



def resend_customer_otp(request, subdomain, email):
    subdomain = subdomain.replace('.platform', '')
    subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
    vendor = subdomain_obj.vendor
    
    try:
        # Verify customer exists for this vendor
        customer = get_object_or_404(Customer, email=email, vendor=vendor)
        
        # Generate new OTP
        new_otp = generate_otp()
        
        # Expire old OTPs
        OTP.objects.filter(email=email, status='active').update(status='expired')
        
        # Create new OTP
        OTP.objects.create(
            email=email,
            otp=str(new_otp),
            status='active'
        )
        
        # Send new OTP
        if send_otp_to_email(email, new_otp):
            messages.success(request, "New verification code has been sent to your email.")
        else:
            messages.error(request, "Failed to send verification code. Please try again.")
            
    except Customer.DoesNotExist:
        messages.error(request, "No account found with this email.")
    
    if 'is_password_reset' in request.GET:
        return redirect('verify_customer_reset_otp', subdomain=subdomain, email=email)
    return redirect('verify_customer_otp', subdomain=subdomain)





def customer_forgot_password(request, subdomain):  # Add subdomain parameter
    sub = subdomain.replace('.platform', '')
    subdomain_obj = get_object_or_404(Subdomain, subdomain=sub)
    vendor = subdomain_obj.vendor
    
    if request.method == "POST":
        email = request.POST.get('email')
        try:
            # Ensure the customer exists and is associated with the current vendor
            customer = Customer.objects.get(email=email, vendor=vendor)
            
            # Generate an OTP: expire previous ones
            otp_val = generate_otp()
            OTP.objects.filter(email=email, status='active').update(status='expired')
            OTP.objects.create(email=email, otp=str(otp_val), status='active')
            
            if send_otp_to_email(email, otp_val):
                messages.success(request, "Password reset OTP has been sent to your email.")
                request.session['pending_customer_email'] = email
                return redirect('verify_customer_reset_otp', subdomain=subdomain, email=email)
            else:
                messages.error(request, "Failed to send OTP. Please try again.")
                
        except Customer.DoesNotExist:
            messages.error(request, "No customer account found with this email address.")
            return redirect('customer_forgot_password', subdomain=subdomain)
            
    return render(request, 'accounts/customer_forgotpassword.html', {
        'vendor': vendor,
        'subdomain': subdomain
    })





def verify_customer_reset_otp(request, subdomain, email):
    sub = subdomain.replace('.platform', '')
    subdomain_obj = get_object_or_404(Subdomain, subdomain=sub)
    vendor = subdomain_obj.vendor
    
    if request.method == "POST":
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            otp_input = form.cleaned_data['otp']
            try:
                otp_obj = OTP.objects.get(email=email, status='active')
                if otp_obj.is_valid(otp_input):
                    otp_obj.mark_as_used()
                    messages.success(request, "OTP verified successfully")
                    # Add debug print
                    print(f"Redirecting to reset password with subdomain: {subdomain}, email: {email}")
                    return redirect('reset_customer_password', subdomain=subdomain, email=email)
                else:
                    messages.error(request, "Invalid or expired OTP")
            except OTP.DoesNotExist:
                messages.error(request, "No active OTP found")
        else:
            messages.error(request, "Invalid OTP format")
    
    return render(request, 'accounts/customer_otp_verification.html', {
        'form': OTPVerificationForm(),
        'email': email,
        'is_password_reset': True,
        'vendor': vendor
    })
    

def reset_customer_password(request, subdomain, email):  # Add subdomain parameter
    # Get vendor from subdomain
    sub = subdomain.replace('.platform', '')
    subdomain_obj = get_object_or_404(Subdomain, subdomain=sub)
    vendor = subdomain_obj.vendor

    if request.method == "POST":
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return render(request, 'accounts/customer_reset_password.html', {
                'email': email,
                'vendor': vendor
            })
        try:
            # Check if customer belongs to this vendor
            customer = Customer.objects.get(email=email, vendor=vendor)
            customer.set_password(password1)
            customer.save()
            messages.success(request, "Password reset successfully")
            return redirect('customer_login', subdomain=subdomain)
        except Customer.DoesNotExist:
            messages.error(request, "Customer not found")
            return redirect('customer_login', subdomain=subdomain)

    return render(request, 'accounts/customer_reset_password.html', {
        'email': email,
        'vendor': vendor
    })
