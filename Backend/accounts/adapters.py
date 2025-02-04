from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from .models import Vendor

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        vendor = super().save_user(request, sociallogin, form)
        
        # Set default values for required fields if they're not provided
        if not vendor.phone_number:
            vendor.phone_number = None  # Or any default value you prefer
        if not vendor.first_name:
            vendor.first_name = ''  # Or any default value you prefer
        if not vendor.last_name:
            vendor.last_name = ''  # Or any default value you prefer
            
        vendor.save()
        return vendor

from allauth.account.adapter import DefaultAccountAdapter
from django.shortcuts import redirect

class MyAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        return super().get_login_redirect_url(request)

    def respond_social_login_failure(self, request, sociallogin):
        return redirect('/custom-error-page/')  # Replace with your error page URL