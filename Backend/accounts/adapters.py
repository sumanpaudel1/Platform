from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from django.shortcuts import redirect
from .models import Vendor

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        email = sociallogin.account.extra_data['email']
        try:
            vendor = Vendor.objects.get(email=email)
            sociallogin.connect(request, vendor)
        except Vendor.DoesNotExist:
            pass
    
    def save_user(self, request, sociallogin, form=None):
        vendor = super().save_user(request, sociallogin, form)
        data = sociallogin.account.extra_data
        vendor.email = data.get('email')
        vendor.first_name = data.get('given_name', '')
        vendor.last_name = data.get('family_name', '')
        vendor.is_verified = True
        vendor.save()
        return vendor

class CustomAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        return '/dashboard/'
    
    def get_signup_redirect_url(self, request):
        return '/dashboard/'