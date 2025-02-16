from django.contrib.auth.backends import ModelBackend
from .models import Customer, Subdomain

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password or not request:
            return None
            
        try:
            # Get subdomain from request
            host = request.get_host().split(':')[0]
            subdomain = host.split('.')[0]
            
            # Get vendor from subdomain
            subdomain_obj = Subdomain.objects.get(subdomain=subdomain)
            
            # Get customer specific to this vendor
            customer = Customer.objects.get(
                email=username,
                vendor=subdomain_obj.vendor,
                is_active=True
            )
            
            if customer.check_password(password):
                return customer
                
            return None
            
        except (Customer.DoesNotExist, Subdomain.DoesNotExist):
            return None
        except Exception as e:
            print(f"Authentication error: {str(e)}")
            return None

    def get_user(self, user_id):
        try:
            return Customer.objects.get(pk=user_id)
        except Customer.DoesNotExist:
            return None