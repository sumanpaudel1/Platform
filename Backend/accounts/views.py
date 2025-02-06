from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from .forms import RegistrationForm, LoginForm, VendorProfileForm
from .models import Vendor, OTP, VendorProfile
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

@login_required
def vendor_profile(request):
    vendor = request.user
    try:
        profile = vendor.profile
        is_new = False
    except VendorProfile.DoesNotExist:
        profile = None
        is_new = True

    if request.method == "POST":
        form = VendorProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.vendor = vendor
            profile.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('vendor_dashboard')
    else:
        form = VendorProfileForm(instance=profile)

    return render(request, 'accounts/profile.html', {
        'form': form,
        'profile': profile,
        'is_new': is_new
    })