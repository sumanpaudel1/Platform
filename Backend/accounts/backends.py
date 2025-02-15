from django.contrib.auth.backends import ModelBackend
from .models import Customer

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Try to find the user by email
            customer = Customer.objects.get(email=username)
            if customer.check_password(password):
                return customer
            return None
        except Customer.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return Customer.objects.get(pk=user_id)
        except Customer.DoesNotExist:
            return None