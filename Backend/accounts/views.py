import json
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .forms import RegistrationForm, LoginForm, VendorProfileForm, VendorSettingForm
from .models import Vendor, OTP, VendorProfile, StorePhoto, VendorSetting, CoverPhoto, Subdomain
from .utils import generate_otp, send_otp_to_email
from django.utils import timezone
from django.http import JsonResponse
from .models import Subscription, SubscriptionPlan, SubscriptionPayment
from products.utils import EsewaPayment
import time
import json
from django.urls import reverse
import uuid
import base64
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages


from .models import Subscription, SubscriptionPlan, SubscriptionPayment
# Make sure EsewaPayment class is imported and working

# First, modify your register function to add the free trial
def register(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            vendor = form.save(commit=False)
            vendor.set_password(form.cleaned_data['password1'])
            vendor.is_verified = False
            vendor.save()

            # Create a 10-day free trial subscription for the new vendor
            end_date = timezone.now() + timezone.timedelta(days=10)
            Subscription.objects.create(
                vendor=vendor,
                status='trial',
                start_date=timezone.now(),
                end_date=end_date,
                is_trial=True
            )

            otp = generate_otp()
            send_otp_to_email(vendor.email, otp)
            OTP.objects.create(email=vendor.email, otp=otp)

            return redirect('accounts:verify_otp', email=vendor.email)
    else:
        form = RegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})

# Add this view to handle subscription selection and payment initiation
@login_required
def subscription_plans(request):
    # Get all subscription plans
    plans = {
        'monthly': SubscriptionPlan.objects.filter(period='monthly'),
        'quarterly': SubscriptionPlan.objects.filter(period='quarterly'),
        'annual': SubscriptionPlan.objects.filter(period='annual'),
    }
    
    # Get vendor's current subscription
    try:
        current_subscription = request.user.subscription
    except:
        # Create a trial subscription if none exists
        end_date = timezone.now() + timezone.timedelta(days=10)
        current_subscription = Subscription.objects.create(
            vendor=request.user,
            status='trial',
            start_date=timezone.now(),
            end_date=end_date,
            is_trial=True
        )
    
    context = {
        'plans': plans,
        'subscription': current_subscription,
        'active_tab': 'subscription'
    }
    
    return render(request, 'accounts/subscription_plans.html', context)



@login_required
def subscription_esewa_payment(request, plan_id):
    try:
        # Get the plan
        plan = get_object_or_404(SubscriptionPlan, id=plan_id)
        print(f"Found plan: {plan.name}, price: {plan.price}")
        
        # Generate a transaction ID
        import time
        transaction_id = f"SUB-{request.user.id}-{plan.id}-{int(time.time())}"
        
        # Store payment data in session
        request.session['subscription_payment'] = {
            'plan_id': plan.id,
            'transaction_id': transaction_id,
            'amount': str(plan.price)
        }
        
        # Create a simple data object for the payment class
        class SubscriptionData:
            def __init__(self, transaction_id, price):
                self.transaction_id = transaction_id
                self.price = price
        
        subscription_data = SubscriptionData(transaction_id, plan.price)
        
        # Use the specialized subscription payment handler
        from .utils import EsewaSubscriptionPayment
        esewa = EsewaSubscriptionPayment()
        payment_url, params = esewa.generate_payment_data(subscription_data)
        
        print(f"Payment params: {params}")
        print(f"Payment URL: {payment_url}")
        
        # Render the template with payment data - properly formatted for v2 API
        return render(request, 'accounts/subscription_redirect.html', {
            'payment_url': payment_url,
            'params': params
        })
        
    except Exception as e:
        print(f"ERROR in subscription_esewa_payment: {str(e)}")
        import traceback
        traceback.print_exc()
        messages.error(request, f"Error initiating payment: {str(e)}")
        return redirect('accounts:subscription_plans')

# Add this view to handle successful eSewa payment@csrf_exempt
@csrf_exempt
def subscription_payment_success(request):
    try:
        print("eSewa success callback received")
        print(f"Request GET data: {request.GET}")
        
        # eSewa returns these parameters
        ref_id = request.GET.get('refId', '')
        transaction_id = request.GET.get('oid', '')
        amount = request.GET.get('amt', '')
        
        print(f"Payment details - refId: {ref_id}, oid: {transaction_id}, amount: {amount}")
        
        # Get subscription data from session
        subscription_data = request.session.get('subscription_payment')
        print(f"Session data: {subscription_data}")
        
        if not subscription_data:
            messages.error(request, "No pending subscription payment found")
            return redirect('accounts:subscription_plans')
        
        # Get the plan
        plan_id = subscription_data.get('plan_id')
        plan = get_object_or_404(SubscriptionPlan, id=plan_id)
        
        # Get or create subscription record
        try:
            subscription = Subscription.objects.get(vendor=request.user)
        except Subscription.DoesNotExist:
            subscription = Subscription(vendor=request.user)
        
        # Update subscription details
        now = timezone.now()
        subscription.plan = plan
        subscription.status = 'active'
        subscription.is_trial = False
        subscription.start_date = now
        subscription.transaction_id = ref_id  # Use the eSewa reference ID
        subscription.last_payment_date = now
        
        # Calculate end date based on plan period
        if plan.period == 'monthly':
            subscription.end_date = now + timezone.timedelta(days=30)
        elif plan.period == 'quarterly':
            subscription.end_date = now + timezone.timedelta(days=90)
        elif plan.period == 'annual':
            subscription.end_date = now + timezone.timedelta(days=365)
        
        subscription.save()
        
        # Record the payment with robust error handling
        try:
            # Convert request.GET to dict for JSON serialization
            response_dict = {key: request.GET.get(key) for key in request.GET.keys()}
            
            # Create payment record
            payment = SubscriptionPayment.objects.create(
                subscription=subscription,
                amount=float(amount) if amount else 0.00,
                transaction_id=ref_id,
                status='completed',
                payment_method='esewa',
                response_data=response_dict
            )
            
            print(f"Payment record created successfully: {payment.id}")
        except Exception as payment_error:
            print(f"ERROR creating payment record: {str(payment_error)}")
            import traceback
            traceback.print_exc()
        
        # Enable subdomain
        try:
            vendor_settings = VendorSetting.objects.get(vendor=request.user)
            subdomain = Subdomain.objects.filter(vendor=request.user).first()
            
            if subdomain and not vendor_settings.is_subdomain_active:
                vendor_settings.is_subdomain_active = True
                vendor_settings.save()
                
                # Create notification
                Notification.objects.create(
                    vendor=request.user,
                    message=f"Your subscription has been renewed. Your subdomain {subdomain.subdomain}.platform is active again.",
                    notification_type='subscription_update'
                )
        except (VendorSetting.DoesNotExist, Subdomain.DoesNotExist):
            pass
        
        # Clear session data
        if 'subscription_payment' in request.session:
            del request.session['subscription_payment']
        
        # Show success message and redirect to dashboard
        messages.success(request, f"You have successfully subscribed to the {plan.name} plan!")
        return redirect('accounts:vendor_dashboard')
        
    except Exception as e:
        print(f"ERROR in subscription_payment_success: {str(e)}")
        import traceback
        traceback.print_exc()
        messages.error(request, f"Error processing payment: {str(e)}")
        return redirect('accounts:subscription_plans')

# Add this view to handle failed eSewa payment
@csrf_exempt
def subscription_payment_failure(request):
    # Clear session data
    if 'pending_subscription' in request.session:
        del request.session['pending_subscription']
        
    messages.error(request, "Subscription payment failed or was cancelled.")
    return redirect('accounts:subscription_plans')



def check_subscription_middleware(get_response):
    def middleware(request):
        if request.user.is_authenticated and hasattr(request.user, 'subscription'):
            subscription = request.user.subscription
            
            # Check if subscription is expired
            if subscription.end_date < timezone.now() and subscription.status != 'expired':
                subscription.status = 'expired'
                subscription.save()
                
                # Disable subdomain
                try:
                    vendor_settings = VendorSetting.objects.get(vendor=request.user)
                    if vendor_settings.is_subdomain_active:
                        vendor_settings.is_subdomain_active = False
                        vendor_settings.save()
                        
                        # Create notification for vendor
                        Notification.objects.create(
                            vendor=request.user,
                            message="Your subscription has expired. Your subdomain has been deactivated.",
                            notification_type='subscription_update'
                        )
                except VendorSetting.DoesNotExist:
                    pass
                
                # If not on subscription page, redirect to it with a message
                if request.path != reverse('accounts:subscription_plans') and 'admin' not in request.path:
                    messages.error(request, "Your subscription has expired. Please renew to continue using all features.")
                    return redirect('accounts:subscription_plans')
        
        response = get_response(request)
        return response
    
    return middleware  # This return statement was missing

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
                return redirect('accounts:login')
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
                        return redirect('accounts:vendor_dashboard')
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


from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_vendor(request):
    logout(request)
    return redirect('accounts:login')

from django.shortcuts import redirect
from django.contrib import messages
import logging
from .models import OTP
from .utils import generate_otp

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
    
    return redirect('accounts:verify_otp', email=email)

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
            return redirect('accounts:forgot_password')
    
    return render(request, 'accounts/forgot_password.html')

def verify_reset_otp(request, email):
    if request.method == "POST":
        otp_digits = [request.POST.get(f'otp{i}', '') for i in range(1, 7)]
        entered_otp = ''.join(otp_digits)
        
        try:
            otp_entry = OTP.objects.filter(email=email, status='active').latest('created_at')
            
            if otp_entry.is_valid(entered_otp):
                otp_entry.mark_as_used()
                return redirect('accounts:reset_password', email=email)
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
            return redirect('accounts:login')
            
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
            return redirect('accounts:vendor_profile')
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
from .models import Vendor, OTP, VendorProfile, StorePhoto, VendorSetting, CoverPhoto, Subdomain, CollectionImage
@login_required
def store_settings(request):
    # Get or create settings for vendor
    try:
        settings = VendorSetting.objects.get(vendor=request.user)
    except VendorSetting.DoesNotExist:
        settings = VendorSetting(vendor=request.user)
        settings.save()

    # Get collection images
    collection_images = {}
    for collection_type in ['new_arrivals', 'best_sellers', 'season_special']:
        try:
            collection_images[collection_type] = CollectionImage.objects.get(
                vendor_setting=settings, 
                collection_type=collection_type
            )
        except CollectionImage.DoesNotExist:
            collection_images[collection_type] = None

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

        # Handle collection images
        for collection_type, field_prefix in [
            ('new_arrivals', 'new_arrivals_'),
            ('best_sellers', 'best_sellers_'),
            ('season_special', 'season_special_')
        ]:
            # Get or create collection image object
            collection_obj, created = CollectionImage.objects.get_or_create(
                vendor_setting=settings,
                collection_type=collection_type,
                defaults={
                    'title': request.POST.get(f'{field_prefix}title', ''),
                    'subtitle': request.POST.get(f'{field_prefix}subtitle', '')
                }
            )
            
            # Update existing collection if not created
            if not created:
                collection_obj.title = request.POST.get(f'{field_prefix}title', collection_obj.title)
                collection_obj.subtitle = request.POST.get(f'{field_prefix}subtitle', collection_obj.subtitle)
            
            # Handle image upload
            image_field = f'{field_prefix}image'
            if request.FILES.get(image_field):
                collection_obj.image = request.FILES[image_field]
                collection_obj.save()

        try:
            settings.save()
            messages.success(request, 'Settings updated successfully!')
        except Exception as e:
            messages.error(request, f'Error saving settings: {str(e)}')
        
        return redirect('accounts:vendor_settings')

    context = {
        'settings': settings,
        'cover_photos': settings.cover_photos.all() if settings.id else [],
        'new_arrivals_collection': collection_images['new_arrivals'],
        'best_sellers_collection': collection_images['best_sellers'],
        'season_special_collection': collection_images['season_special'],
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
    return redirect('accounts:vendor_settings')



#Product views

from products.vector_database import VectorDatabase

# Create global instance with proper initialization
try:
    vector_db = VectorDatabase()
    print("Vector database initialized successfully")
except Exception as e:
    print(f"Error initializing vector database: {str(e)}")
    vector_db = None




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






@login_required
def vendor_product_edit(request, pk):
    """View for editing a vendor's product"""
    product = get_object_or_404(Product, pk=pk, vendor=request.user)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save()
            
            # Handle product images with Cloudinary
            if request.FILES.getlist('product_images'):
                for image in request.FILES.getlist('product_images'):
                    # Upload to Cloudinary
                    cloudinary_response = upload_product_image(
                        image, 
                        vendor_id=request.user.id, 
                        product_id=product.id
                    )
                    
                    if cloudinary_response:
                        # Create ProductImage with Cloudinary data
                        ProductImage.objects.create(
                            product=product,
                            image=image,  # Keep for backward compatibility
                            image_url=cloudinary_response['url'],
                            public_id=cloudinary_response['public_id']
                        )
                    else:
                        # Fall back to regular upload if Cloudinary fails
                        ProductImage.objects.create(
                            product=product,
                            image=image
                        )

                try:
                    vector_db.index_product_images(request.user.id, [product])
                    print(f"Vector index updated for product {product.id}")
                except Exception as e:
                    print(f"Error updating index: {str(e)}")
                    
            # Handle color and size variants (existing code)
            product.color_variant.set(request.POST.getlist('color_variants'))
            product.size_variant.set(request.POST.getlist('size_variants'))

            messages.success(request, 'Product updated successfully!')
            return redirect('accounts:vendor_products')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ProductForm(instance=product)
    
    # Your existing render code
    context = {
        'form': form,
        'product': product,
        'category_form': CategoryForm(),
        'color_form': ProductColorVariantForm(),
        'size_form': ProductSizeVariantForm(),
        'categories': Category.objects.all(),
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
            
            product = image.product
            image.delete()
            
            if product.product_images.exists():
                try:
                    vector_db.index_product_images(request.user.id, [product])
                    print(f"Vector index updated after image deletion for product {product.id}")
                except Exception as e:
                    print(f"Error updating index: {str(e)}")
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
        return redirect('accounts:vendor_products')
    
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
            
            # Handle uploaded images with Cloudinary
            images = request.FILES.getlist('product_images')
            for image in images:
                # Upload to Cloudinary
                cloudinary_response = upload_product_image(
                    image, 
                    vendor_id=request.user.id, 
                    product_id=product.id
                )
                
                if cloudinary_response:
                    # Create ProductImage with Cloudinary data
                    ProductImage.objects.create(
                        product=product,
                        image=image,  # Keep for backward compatibility
                        image_url=cloudinary_response['url'],
                        public_id=cloudinary_response['public_id']
                    )
                else:
                    # Fall back to regular upload if Cloudinary fails
                    ProductImage.objects.create(
                        product=product,
                        image=image
                    )

            try:
                vector_db.index_product_images(request.user.id, [product])
                print(f"Vector index created for new product {product.id}")
            except Exception as e:
                print(f"Error indexing new product: {str(e)}")
                
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
            return redirect('accounts:vendor_products')
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
        # 'active_tab': 'products',
    })
    
        
    

from products.utils import upload_product_image, delete_product_image
from products.models import ProductImage
# Import other required modules

# Add Cloudinary upload to add_product_images function
@login_required
def add_product_images(request, pk):
    if request.method == 'POST':
        product = get_object_or_404(Product, pk=pk, vendor=request.user)
        try:
            for image in request.FILES.getlist('product_images'):
                # Upload to Cloudinary
                cloudinary_response = upload_product_image(
                    image, 
                    vendor_id=request.user.id, 
                    product_id=product.id
                )
                
                if cloudinary_response:
                    # Create ProductImage with Cloudinary data
                    ProductImage.objects.create(
                        product=product,
                        image=image,  # Keep for backward compatibility
                        image_url=cloudinary_response['url'],
                        public_id=cloudinary_response['public_id']
                    )
                else:
                    # Fall back to regular upload if Cloudinary fails
                    ProductImage.objects.create(
                        product=product,
                        image=image
                    )
                    
            # Update vector index if needed
            try:
                vector_db.index_product_images(request.user.id, [product])
                print(f"Vector index updated after adding images for product {product.id}")
            except Exception as e:
                print(f"Error updating index: {str(e)}")
                
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

# Update the delete_product_image view to handle Cloudinary
@login_required
def delete_product_image(request, image_id):
    if request.method == 'POST':
        try:
            image = get_object_or_404(ProductImage, 
                                    id=image_id, 
                                    product__vendor=request.user)
            
            product = image.product
            
            # Delete from Cloudinary if public_id exists
            if image.public_id:
                delete_product_image(image.public_id)
            
            # Delete from database
            image.delete()
            
            if product.product_images.exists():
                try:
                    vector_db.index_product_images(request.user.id, [product])
                    print(f"Vector index updated after image deletion for product {product.id}")
                except Exception as e:
                    print(f"Error updating index: {str(e)}")
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
from .utils import generate_otp, send_customer_otp_to_email
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
                
                if send_customer_otp_to_email(customer.email, otp_val, vendor):
                    messages.success(request, 
                        "Registration successful! Please check your email for verification code.")
                    return redirect('accounts:verify_customer_otp', subdomain=subdomain)
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
        return redirect('accounts:customer_register', subdomain=subdomain)

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
            
            return redirect('accounts:verify_customer_otp', subdomain=subdomain)
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
        
        try:
            subdomain_obj = Subdomain.objects.get(subdomain=subdomain)
            vendor = subdomain_obj.vendor
            
            # Check session data first
            customer_id = request.session.get('customer_id')
            print(f"Checking session data - customer_id: {customer_id}")
            
            if customer_id:
                try:
                    customer = Customer.objects.get(
                        id=customer_id,
                        vendor=vendor,
                        is_active=True
                    )
                    # Add customer to request
                    request.customer = customer
                    # Ensure user is authenticated
                    if not request.user.is_authenticated:
                        login(request, customer, backend='django.contrib.auth.backends.ModelBackend')
                    return view_func(request, *args, **kwargs)
                except Customer.DoesNotExist:
                    print(f"Customer with ID {customer_id} not found")
                    pass
            
            # Clear invalid session and redirect
            print("No valid customer found in session")
            request.session.flush()
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
        # Get the most recently registered customer using date_joined instead of created_at
        customer = Customer.objects.filter(
            email=email, 
            vendor=vendor
        ).latest('date_joined')  # Changed from created_at to date_joined
        
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
        if send_customer_otp_to_email(customer.email, new_otp, vendor):
            messages.success(request, "New verification code has been sent to your email.")
        else:
            messages.error(request, "Failed to send verification code. Please try again.")
            
    except Customer.DoesNotExist:
        messages.error(request, "No account found with this email.")
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
    
    # Determine where to redirect based on the context
    if 'is_password_reset' in request.GET:
        return redirect('accounts:verify_customer_reset_otp', subdomain=subdomain, email=email)
    return redirect('accounts:verify_customer_otp', subdomain=subdomain)


 

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
            
            if send_customer_otp_to_email(customer.email, otp_val, vendor):
                messages.success(request, "Password reset OTP has been sent to your email.")
                request.session['pending_customer_email'] = email
                return redirect('accounts:verify_customer_reset_otp', subdomain=subdomain, email=email)
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
                # First verify OTP
                otp_obj = OTP.objects.get(email=email, status='active')
                
                # Check if customer exists for this vendor
                customer = Customer.objects.get(email=email, vendor=vendor)
                
                if otp_obj.is_valid(otp_input):
                    otp_obj.mark_as_used()
                    messages.success(request, "OTP verified successfully")
                    
                    # Store email in session for password reset
                    request.session['reset_email'] = email
                    
                    # Debug prints
                    print(f"OTP verified for email: {email}")
                    print(f"Redirecting to reset password page")
                    
                    return redirect('accounts:reset_customer_password', 
                                  subdomain=subdomain, 
                                  email=email)
                else:
                    messages.error(request, "Invalid or expired OTP")
            except OTP.DoesNotExist:
                messages.error(request, "No active OTP found")
            except Customer.DoesNotExist:
                messages.error(request, "No account found with this email")
            except Exception as e:
                print(f"Error in verify_customer_reset_otp: {str(e)}")
                messages.error(request, "An error occurred during verification")
    
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
            return redirect('accounts:customer_login', subdomain=subdomain)
        except Customer.DoesNotExist:
            messages.error(request, "Customer not found")
            return redirect('accounts:customer_login', subdomain=subdomain)

    return render(request, 'accounts/customer_reset_password.html', {
        'email': email,
        'vendor': vendor
    })



from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages

def customer_logout(request, subdomain):
    logout(request)
    request.session.flush()
    messages.success(request, "Successfully logged out")
    return redirect(f'/{subdomain}.platform/customer/login/')






@vendor_login_required
def customer_profile(request, subdomain):
    subdomain = subdomain.replace('.platform', '')
    subdomain_obj = get_object_or_404(Subdomain, subdomain=subdomain)
    vendor = subdomain_obj.vendor
    
    try:
        customer = Customer.objects.get(id=request.session.get('customer_id'), vendor=vendor)
    except Customer.DoesNotExist:
        messages.error(request, "Please login to access your profile")
        return redirect('accounts:customer_login', subdomain=subdomain)
    
    if request.method == "POST":
        # Update profile
        customer.first_name = request.POST.get('first_name', customer.first_name)
        customer.last_name = request.POST.get('last_name', customer.last_name)
        customer.phone_number = request.POST.get('phone_number', customer.phone_number)
        
        if 'profile_picture' in request.FILES:
            customer.profile_picture = request.FILES['profile_picture']
        
        customer.save()
        messages.success(request, "Profile updated successfully")
        return redirect('accounts:customer_profile', subdomain=subdomain)
    
    return render(request, 'accounts/customer_profile.html', {
        'customer': customer,
        'vendor': vendor
    })
    
    



from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum
from products.models import Order, Wishlist
from .models import Customer, Subdomain

@vendor_login_required
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





def vendor_orders(request):
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    
    # Base queryset
    orders = Order.objects.filter(vendor=request.user)
    
    # Apply status filter
    if status_filter != 'all':
        orders = orders.filter(status=status_filter)
    
    # Get statistics
    total_orders = orders.count()
    pending_orders = orders.filter(status='pending').count()
    processing_orders = orders.filter(status='processing').count()
    total_revenue = orders.filter(status='delivered').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    context = {
        'orders': orders.order_by('-created_at'),
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'processing_orders': processing_orders,
        'total_revenue': total_revenue,
        'active_tab': 'orders'
    }
    
    return render(request, 'accounts/vendor_orders.html', context)


from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
import json


@require_http_methods(["POST"])
def update_order_status(request, order_id):
    try:
        data = json.loads(request.body)
        order = Order.objects.get(id=order_id, vendor=request.user)
        
        old_status = order.status
        new_status = data.get('status')
        
        if new_status not in ['pending', 'processing', 'shipped', 'delivered', 'cancelled']:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid status'
            }, status=400)
        
        # Update order status
        order.status = new_status
        order.save()
        
        # Handle stock updates
        if new_status in ['cancelled', 'delivered'] and old_status not in ['cancelled', 'delivered']:
            for item in order.items.all():
                if new_status == 'delivered':
                    item.product.stock -= item.quantity
                else:  # cancelled
                    item.product.stock += item.quantity
                item.product.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Order status updated successfully'
        })
        
    except Order.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Order not found'
        }, status=404)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)




def order_detail(request, order_id):
    order = get_object_or_404(Order.objects.select_related(
        'customer',
        'delivery_address'
    ).prefetch_related(
        'items',
        'items__product',
        'items__product__product_images',
        'items__color',
        'items__size'
    ), id=order_id, vendor=request.user)
    
    context = {
        'order': order,
        'active_tab': 'orders'
    }
    
    return render(request, 'accounts/order_details.html', context)






from django.http import JsonResponse
from .models import Notification

from django.http import JsonResponse

def get_notifications_context(request):
    """Return notifications as JSON response for API calls or context for templates"""
    # ALWAYS RETURN JsonResponse when accessed as a URL endpoint
    if request.path == '/api/notifications/':
        if request.user.is_authenticated:
            try:
                # Get unread count
                unread_count = Notification.objects.filter(
                    vendor=request.user,
                    is_read=False
                ).count()

                # Get recent notifications
                notifications = Notification.objects.filter(
                    vendor=request.user
                ).order_by('-created_at')[:15]

                # Format notifications for JSON response
                notifications_data = []
                for n in notifications:
                    notifications_data.append({
                        'id': n.id,
                        'message': n.message,
                        'is_read': n.is_read,
                        'time_ago': timesince(n.created_at),
                        'order_id': n.order_id,  # Include order_id
                    })

                return JsonResponse({
                    'status': 'success',
                    'notifications': notifications_data,
                    'unread_count': unread_count
                })
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=500)
        return JsonResponse({
            'status': 'error',
            'message': 'User not authenticated'
        }, status=401)

    # For template context usage, return a dictionary
    context = {
        'notifications': [],
        'unread_notifications_count': 0
    }
    
    if request.user.is_authenticated:
        try:
            context['notifications'] = Notification.objects.filter(
                vendor=request.user
            ).order_by('-created_at')[:15]
            
            context['unread_notifications_count'] = Notification.objects.filter(
                vendor=request.user,
                is_read=False
            ).count()
        except Exception as e:
            print(f"Error in notifications context: {str(e)}")
    
    return context


def mark_notifications_as_read(request):
    if request.method == 'POST':
        try:
            # Update all unread notifications for this vendor
            Notification.objects.filter(
                vendor=request.user,
                is_read=False
            ).update(is_read=True)
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=400)
    



from django.db.models.signals import post_save
from django.dispatch import receiver
from products.models import Order
from accounts.models import Notification

def create_order_notification(request, order):
    """Create a notification when a new order is placed"""
    try:
        Notification.objects.create(
            vendor=order.vendor,
            message=f"New order #{order.order_id} received",
            is_read=False,
            order_id=order.id  # Include the order ID
        )
    except Exception as e:
        print(f"Error creating notification: {str(e)}")
        
        

@login_required
def mark_single_notification_as_read(request, notification_id):
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(
                id=notification_id,
                vendor=request.user
            )
            notification.is_read = True
            notification.save()
            
            # Count remaining unread notifications
            unread_count = Notification.objects.filter(
                vendor=request.user,
                is_read=False
            ).count()
            
            return JsonResponse({
                'status': 'success',
                'unread_count': unread_count
            })
        except Notification.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Notification not found'
            }, status=404)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=400)
    
    
    


from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from datetime import datetime, timedelta
import json
from products.models import Product, Order


@login_required(login_url='accounts:login')
def vendor_dashboard(request):
    try:
        # Basic statistics
        total_products = Product.objects.filter(vendor=request.user).count()
        active_products = Product.objects.filter(vendor=request.user, stock__gt=0).count()
        low_stock_count = Product.objects.filter(vendor=request.user, stock__lte=10).count()
        
        # Orders statistics
        orders = Order.objects.filter(vendor=request.user)
        total_orders = orders.count()
        recent_orders = orders.select_related('customer').order_by('-created_at')[:5]
        
        # Revenue calculations
        total_revenue = orders.filter(status='delivered').aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        # Get last month's data
        last_month = timezone.now() - timezone.timedelta(days=30)
        last_month_revenue = orders.filter(
            status='delivered',
            created_at__gte=last_month
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Calculate growth rates
        revenue_growth = ((total_revenue - last_month_revenue) / last_month_revenue * 100) if last_month_revenue else 0
        
        # Get top products
        top_products = Product.objects.filter(vendor=request.user)\
            .annotate(
                total_sales=Count('orderitem'),
                revenue=Sum('orderitem__price')
            ).order_by('-total_sales')[:5]
        
        # Order status counts - Fixed this part
        status_counts = {
            'pending': orders.filter(status='pending').count(),
            'processing': orders.filter(status='processing').count(),
            'shipped': orders.filter(status='shipped').count(),
            'delivered': orders.filter(status='delivered').count(),
            'cancelled': orders.filter(status='cancelled').count()
        }
        
        # Create ordered list for chart
        order_status_data = [
            status_counts['pending'],
            status_counts['processing'],
            status_counts['shipped'],
            status_counts['delivered'],
            status_counts['cancelled']
        ]
        
        # Monthly sales data
        monthly_sales = orders.filter(status='delivered')\
            .annotate(month=TruncMonth('created_at'))\
            .values('month')\
            .annotate(total=Sum('total_amount'))\
            .order_by('month')
        
        monthly_sales_labels = [item['month'].strftime('%B %Y') for item in monthly_sales]
        monthly_sales_data = [float(item['total']) for item in monthly_sales]
        
        context = {
            'total_revenue': total_revenue,
            'revenue_growth': revenue_growth,
            'total_orders': total_orders,
            'total_products': total_products,
            'active_products': active_products,
            'low_stock_count': low_stock_count,
            'recent_orders': recent_orders,
            'top_products': top_products,
            'monthly_sales_labels': json.dumps(monthly_sales_labels),
            'monthly_sales_data': monthly_sales_data,
            'order_status_data': order_status_data,
            'order_status_labels': ['Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled'],
            'current_date': timezone.now(),
            'active_tab': 'dashboard'  # Add this to highlight dashboard tab
        }
        
        return render(request, 'accounts/vendor_dashboard.html', context)
        
    except Exception as e:
        print(f"Dashboard Error: {str(e)}")  # Add debug print
        messages.error(request, f"Error loading dashboard: {str(e)}")
        return redirect('accounts:Dashboard')
    
    
  
from django.utils.timesince import timesince
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Notification
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import JsonResponse




def create_order_notification(request, order):
    """Create a notification when a new order is placed"""
    try:
        Notification.objects.create(
            vendor=order.vendor,
            message=f"New order #{order.order_id} received",
            is_read=False,
            order_id=order.id  # Include the order ID
        )
    except Exception as e:
        print(f"Error creating notification: {str(e)}")
        
        
   
   
   
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from .models import Vendor, VendorSetting, VendorProfile, Notification

@login_required
def subdomain_management(request):
    """View for managing vendor subdomain"""
    try:
        vendor = request.user
        
        # Check if vendor has settings, create if not
        if not hasattr(vendor, 'settings'):
            VendorSetting.objects.create(
                vendor=vendor,
                store_name=vendor.profile.business_name if hasattr(vendor, 'profile') else f"{vendor.first_name}'s Store"
            )
        
        # Handle form submission
        if request.method == "POST":
            subdomain = request.POST.get('subdomain', '').strip().lower()
            action = request.POST.get('action', 'create')
            
            # Basic validation
            if not subdomain:
                messages.error(request, "Subdomain cannot be empty.")
                return redirect('accounts:subdomain_management')
            
            # More validation (alphanumeric and hyphen only)
            import re
            if not re.match(r'^[a-z0-9-]+$', subdomain):
                messages.error(request, "Subdomain can only contain lowercase letters, numbers, and hyphens.")
                return redirect('accounts:subdomain_management')
            
            # Check if the profile is complete and verified
            if not hasattr(vendor, 'profile') or vendor.profile.profile_status != 'approved' or not vendor.profile.is_verified:
                messages.error(request, "Your profile must be complete and verified before requesting a subdomain.")
                return redirect('accounts:subdomain_management')
            
            # Check availability (exclude current vendor's subdomain if updating)
            existing_subdomain = VendorSetting.objects.filter(subdomain=subdomain).exclude(vendor=vendor).first()
            if existing_subdomain:
                messages.error(request, f"The subdomain '{subdomain}' is already taken. Please choose another one.")
                return redirect('accounts:subdomain_management')
            
            # Process the request
            if action == 'update' and vendor.settings.subdomain:
                # For update requests
                old_subdomain = vendor.settings.subdomain
                
                # Update the subdomain
                vendor.settings.subdomain = subdomain
                vendor.settings.is_subdomain_active = False  # Require re-approval
                vendor.settings.subdomain_request_date = timezone.now()
                vendor.settings.subdomain_approval_date = None
                vendor.settings.save()
                
                # Create notification for admin
                admin_notification = Notification.objects.create(
                    message=f"Vendor {vendor.first_name} {vendor.last_name} requested to change subdomain from '{old_subdomain}' to '{subdomain}'",
                    vendor=None,  # Admin notification
                    is_admin=True,
                    notification_type='subdomain_update'
                )
                
                messages.success(request, "Your subdomain update request has been submitted and is pending approval.")
            else:
                # For new subdomain requests
                vendor.settings.subdomain = subdomain
                vendor.settings.is_subdomain_active = False
                vendor.settings.subdomain_request_date = timezone.now()
                vendor.settings.save()
                
                # Create notification for admin
                admin_notification = Notification.objects.create(
                    message=f"Vendor {vendor.first_name} {vendor.last_name} requested subdomain '{subdomain}'",
                    vendor=None,  # Admin notification
                    is_admin=True,
                    notification_type='subdomain_request'
                )
                
                messages.success(request, "Your subdomain request has been submitted and is pending approval.")
            
            return redirect('accounts:subdomain_management')
        
        context = {
            'vendor': vendor,
        }
        
        return render(request, 'accounts/subdomain.html', context)
    
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('accounts:vendor_dashboard')
    
    


@login_required
def admin_subdomain_requests(request):
    """Admin view for managing subdomain requests"""
    # Check if user is admin
    if not request.user.is_admin and not request.user.is_staff:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('accounts:dashboard')
    
    # Get all pending subdomain requests
    pending_requests = VendorSetting.objects.filter(
        is_subdomain_active=False,
        subdomain__isnull=False,
        subdomain_approval_date__isnull=True
    ).select_related('vendor').order_by('-subdomain_request_date')
    
    # Handle approval/rejection
    if request.method == "POST":
        vendor_id = request.POST.get('vendor_id')
        action = request.POST.get('action')
        
        if not vendor_id or not action:
            messages.error(request, "Invalid request.")
            return redirect('accounts:admin_subdomain_requests')
        
        try:
            vendor = Vendor.objects.get(id=vendor_id)
            vendor_settings = vendor.settings
            
            if action == 'approve':
                # Approve the subdomain
                vendor_settings.is_subdomain_active = True
                vendor_settings.subdomain_approval_date = timezone.now()
                vendor_settings.save()
                
                # Create notification for vendor
                Notification.objects.create(
                    message=f"Your subdomain request '{vendor_settings.subdomain}.platform' has been approved!",
                    vendor=vendor,
                    notification_type='general'
                )
                
                messages.success(request, f"Subdomain '{vendor_settings.subdomain}' has been approved.")
                
            elif action == 'reject':
                rejection_reason = request.POST.get('rejection_reason', 'Your subdomain request was rejected.')
                old_subdomain = vendor_settings.subdomain
                
                # Reset the subdomain
                vendor_settings.is_subdomain_active = False
                vendor_settings.subdomain = None
                vendor_settings.save()
                
                # Create notification for vendor
                Notification.objects.create(
                    message=f"Your subdomain request '{old_subdomain}.platform' was rejected: {rejection_reason}",
                    vendor=vendor,
                    notification_type='general'
                )
                
                messages.success(request, f"Subdomain '{old_subdomain}' has been rejected.")
            
            # Mark related admin notifications as read
            Notification.objects.filter(
                is_admin=True,
                notification_type__in=['subdomain_request', 'subdomain_update'],
                related_vendor_id=vendor_id,
                is_read=False
            ).update(is_read=True)
                
        except Vendor.DoesNotExist:
            messages.error(request, "Vendor not found.")
        except Exception as e:
            messages.error(request, f"Error processing request: {str(e)}")
    
    context = {
        'pending_requests': pending_requests
    }
    
    return render(request, 'accounts/admin_subdomain_requests.html', context)



# In accounts/views.py (line 2199)
def landing_page(request):
    """Display the landing page for vendors"""
    return render(request, 'accounts/landingpage.html')


# Add CollectionImage to this import statement
from .models import Vendor, OTP, VendorProfile, StorePhoto, VendorSetting, CoverPhoto, Subdomain, CollectionImage
from .utils import generate_otp, send_otp_to_email





@login_required
def subscription_plans(request):
    """View to display available subscription plans"""
    # Get all subscription plans
    plans = {
        'monthly': SubscriptionPlan.objects.filter(period='monthly'),
        'quarterly': SubscriptionPlan.objects.filter(period='quarterly'),
        'annual': SubscriptionPlan.objects.filter(period='annual'),
    }
    
    # Get vendor's current subscription
    try:
        current_subscription = Subscription.objects.get(vendor=request.user)
    except Subscription.DoesNotExist:
        # Create a trial subscription if none exists
        end_date = timezone.now() + timezone.timedelta(days=10)
        current_subscription = Subscription.objects.create(
            vendor=request.user,
            status='trial',
            start_date=timezone.now(),
            end_date=end_date,
            is_trial=True
        )
    
    # Calculate days remaining in subscription
    now = timezone.now()
    if current_subscription.end_date > now:
        days_remaining = (current_subscription.end_date - now).days
    else:
        days_remaining = 0
        # Update subscription status if it has expired
        if current_subscription.status != 'expired':
            current_subscription.status = 'expired'
            current_subscription.save()
            
            # Disable subdomain if subscription expired
            try:
                vendor_settings = VendorSetting.objects.get(vendor=request.user)
                if vendor_settings.is_subdomain_active:
                    vendor_settings.is_subdomain_active = False
                    vendor_settings.save()
                    
                    # Create notification for vendor
                    Notification.objects.create(
                        vendor=request.user,
                        message="Your subscription has expired. Your subdomain has been deactivated.",
                        notification_type='subscription_update'
                    )
            except VendorSetting.DoesNotExist:
                pass
    
    # Don't assign to the property, pass it to the context instead
    context = {
        'plans': plans,
        'subscription': current_subscription,
        'days_remaining': days_remaining,  # Pass as separate context variable
        'active_tab': 'subscription'
    }
    
    return render(request, 'accounts/subscription_plans.html', context)




@login_required
def vendor_subscription_tab(request):
    """View to display subscription details in vendor dashboard"""
    try:
        # Get vendor's subscription
        subscription = get_object_or_404(Subscription, vendor=request.user)
        
        from .utils import sync_subscription_and_subdomain_status
        sync_subscription_and_subdomain_status(request.user)
        
        # Calculate days remaining
        now = timezone.now()
        if subscription.end_date > now:
            days_remaining = (subscription.end_date - now).days
        else:
            days_remaining = 0
            
        # Get subdomain information
        try:
            vendor_settings = VendorSetting.objects.get(vendor=request.user)
            subdomain = Subdomain.objects.filter(vendor=request.user).first()
            subdomain_active = vendor_settings.is_subdomain_active and subdomain is not None
        except (VendorSetting.DoesNotExist, Subdomain.DoesNotExist):
            subdomain_active = False
            subdomain = None
        
        # Get payment history - Force evaluation to debug
        payment_records = list(SubscriptionPayment.objects.filter(
            subscription=subscription
        ).order_by('-payment_date'))
        
        print(f"Found {len(payment_records)} payment records for {request.user.email}")
        
        # Context with all necessary information
        context = {
            'subscription': subscription,
            'days_remaining': days_remaining,
            'subdomain': subdomain,
            'subdomain_active': subdomain_active,
            'payment_records': payment_records,
            'active_tab': 'subscription'
        }
        
    except Subscription.DoesNotExist:
        subscription = None
        context = {
            'subscription': None,
            'active_tab': 'subscription'
        }
    
    return render(request, 'accounts/subscription_tab.html', context)




@login_required
def subscription_payment_process(request, plan_id):
    """Process subscription payment"""
    try:
        # Get the subscription plan
        plan = get_object_or_404(SubscriptionPlan, id=plan_id)
        
        # Get the period from the request
        period = request.GET.get('period', 'monthly')
        
        # Determine price based on period
        if period == 'monthly':
            price = plan.price  # Base price is monthly
        elif period == 'quarterly':
            if plan.name == "Professional":
                price = 139.00
            elif plan.name == "Enterprise":
                price = 549.00
            else:
                price = 0.00
        elif period == 'annual':
            if plan.name == "Professional":
                price = 470.00
            elif plan.name == "Enterprise":
                price = 1990.00
            else:
                price = 0.00
        else:
            price = plan.price  # Default to monthly
        
        # Generate a transaction UUID
        transaction_uuid = str(uuid.uuid4())
        
        # Store payment info in session
        request.session['subscription_payment'] = {
            'plan_id': plan.id,
            'period': period,
            'price': float(price),
            'transaction_uuid': transaction_uuid
        }
        
        # Create context with payment data
        context = {
            'plan': plan,
            'period': period,
            'price': price,
            'transaction_uuid': transaction_uuid
        }
        
        return render(request, 'accounts/subscription_payment.html', context)
        
    except Exception as e:
        messages.error(request, f"Error processing subscription: {str(e)}")
        return redirect('accounts:subscription_plans')
    
    


from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from products.models import Review

@login_required
def vendor_reviews(request, subdomain):
    # list all reviews for this vendor’s products
    reviews = Review.objects.filter(
        product__vendor=request.user
    ).select_related('customer','product').prefetch_related('images')
    return render(request, 'accounts/vendor_reviews.html', {
        'reviews': reviews,
        'subdomain': subdomain
    })

@login_required
def vendor_reply(request, subdomain, review_id):
    if request.method == 'POST':
        rev = get_object_or_404(
            Review, 
            id=review_id, 
            product__vendor=request.user
        )
        rev.reply = request.POST.get('reply','').strip()
        rev.save()
    return redirect('accounts:vendor_reviews', subdomain=subdomain)