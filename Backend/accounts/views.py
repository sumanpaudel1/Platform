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