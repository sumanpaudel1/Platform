import random
from django.core.mail import send_mail
from django.conf import settings
import logging
from accounts.models import VendorSetting, Vendor, Subscription, Subdomain, Notification
import hmac
import hashlib
import base64
import uuid
import time
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

def generate_otp():
    try:
        return random.randint(100000, 999999)
    except Exception as e:
        logger.error(f"Error generating OTP: {str(e)}")
        raise

def send_otp_to_email(email, otp):
    try:
        subject = "Your OTP Code"
        message = f"Your OTP is {otp}. It expires in 1.5 minutes."
        email_from = settings.EMAIL_HOST_USER
        recipient_list = [email]
        
        sent = send_mail(
            subject,
            message,
            email_from,
            recipient_list,
            fail_silently=False
        )
        
        if sent:
            logger.info(f"OTP sent successfully to {email}")
            return True
        logger.error(f"Failed to send OTP to {email}")
        return False
        
    except Exception as e:
        logger.error(f"Error sending OTP email: {str(e)}")
        raise
    
    
    

def send_customer_otp_to_email(email, otp, vendor):
    try:
        try:
            store_name = vendor.settings.store_name
        except (AttributeError, VendorSetting.DoesNotExist):
            store_name = f"{vendor.first_name}'s Store"
            
        print(store_name)
        subject = f"Your OTP Code for {store_name}"
        message = (
            f"Welcome to {store_name}!\n\n"
            f"Your verification code is: {otp}\n"
            f"This code will expire in 1.5 minutes.\n\n"
            f"If you didn't request this code, please ignore this email."
        )
        email_from = settings.EMAIL_HOST_USER
        recipient_list = [email]
        
        sent = send_mail(
            subject,
            message,
            email_from,
            recipient_list,
            fail_silently=False
        )
        
        if sent:
            logger.info(f"Customer OTP sent successfully to {email} for {store_name}")
            return True
        logger.error(f"Failed to send customer OTP to {email} for {store_name}")
        return False
        
    except Exception as e:
        logger.error(f"Error sending customer OTP email: {str(e)}")
        raise
    



from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone

def check_product_limit(request):
    """Check if vendor has reached product limit based on subscription"""
    try:
        from products.models import Product
        
        # Get subscription
        subscription = request.user.subscription
        
        # Default limit for free tier
        product_limit = 10
        
        # If subscription has a plan, get its limit
        if subscription.plan:
            product_limit = subscription.plan.max_products
        
        # Count products
        product_count = Product.objects.filter(vendor=request.user).count()
        
        # Return remaining limit and whether limit is reached
        return {
            'limit': product_limit,
            'used': product_count,
            'remaining': product_limit - product_count,
            'limit_reached': product_count >= product_limit
        }
    except Exception as e:
        # If any error occurs, assume limit not reached
        return {
            'limit': 10,
            'used': 0,
            'remaining': 10, 
            'limit_reached': False
        }

def check_subscription_product_limit(view_func):
    """Decorator to check product limit on add product views"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Only check for product creation (POST without pk)
        if request.method == 'POST' and not kwargs.get('pk'):
            product_limit_info = check_product_limit(request)
            
            if product_limit_info['limit_reached']:
                messages.error(
                    request,
                    f"You've reached your product limit ({product_limit_info['used']}/{product_limit_info['limit']}). "
                    "Please upgrade your subscription to add more products."
                )
                return redirect('accounts:subscription_plans')
                
        return view_func(request, *args, **kwargs)
    return _wrapped_view







import hmac
import hashlib
import base64
import uuid
import time
import random
import string
from datetime import datetime

class EsewaSubscriptionPayment:
    def __init__(self):
        self.merchant_id  = "EPAYTEST"
        self.test_url     = "https://rc-epay.esewa.com.np/api/epay/main/v2/form"
        self.secret_key   = "8gBm/:&EnhH.1/q"

    def generate_signature(self, total_amount, transaction_uuid, product_code):
        msg = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
        h = hmac.new(self.secret_key.encode(), msg.encode(), hashlib.sha256).digest()
        return base64.b64encode(h).decode()

    def generate_payment_data(self, subscription_data, host: str):
        amount = f"{float(subscription_data.price):.2f}"
        txn    = subscription_data.transaction_id
        code   = self.merchant_id

        # only these three get signed, just like in products.utils.EsewaPayment
        signed = ["total_amount", "transaction_uuid", "product_code"]

        params = {
            "amount":                  amount,
            "tax_amount":              "0",
            "total_amount":            amount,
            "transaction_uuid":        txn,
            "product_code":            code,
            "product_service_charge":  "0",
            "product_delivery_charge": "0",
            "success_url":             f"http://{host}/esewa/subscription/success/",
            "failure_url":             f"http://{host}/esewa/subscription/failure/",
            "signed_field_names":      ",".join(signed),
        }

        # build signature over exactly those three
        msg = ",".join(f"{k}={params[k]}" for k in signed)
        sig = hmac.new(
            self.secret_key.encode(),
            msg.encode(),
            hashlib.sha256
        ).digest()
        params["signature"] = base64.b64encode(sig).decode()

        return self.test_url, params

    
    
    



def sync_subscription_and_subdomain_status(vendor):
    """
    Ensures that the subdomain status matches the subscription status
    """
    try:
        # Get subscription and vendor settings
        subscription = Subscription.objects.get(vendor=vendor)
        vendor_settings = VendorSetting.objects.get(vendor=vendor)
        subdomain = Subdomain.objects.filter(vendor=vendor).first()
        
        # Check if subscription is active
        now = timezone.now()
        subscription_active = subscription.status in ['active', 'trial'] and subscription.end_date > now
        
        # If subscription is active but subdomain isn't (and a subdomain exists)
        if subscription_active and not vendor_settings.is_subdomain_active and subdomain and vendor_settings.subdomain:
            vendor_settings.is_subdomain_active = True
            vendor_settings.save()
            
            # Create notification
            Notification.objects.create(
                vendor=vendor,
                message=f"Your subdomain {vendor_settings.subdomain}.platform has been activated.",
                notification_type='subdomain_update'
            )
            return True
        
        # If subscription is not active but subdomain is
        elif not subscription_active and vendor_settings.is_subdomain_active:
            vendor_settings.is_subdomain_active = False
            vendor_settings.save()
            
            # Create notification
            Notification.objects.create(
                vendor=vendor,
                message="Your subdomain has been deactivated due to subscription status.",
                notification_type='subdomain_update'
            )
            return True
            
        return False
    except (Subscription.DoesNotExist, VendorSetting.DoesNotExist):
        return False