from django.utils.deprecation import MiddlewareMixin
from accounts.models import Subdomain

class VendorMiddleware(MiddlewareMixin):
    def process_request(self, request):
        path_parts = request.path.split('/')
        if len(path_parts) > 1:
            # Extract subdomain from URL pattern like "subdomain.platform/home"
            subdomain = path_parts[1].replace('.platform', '')
            try:
                subdomain_obj = Subdomain.objects.get(subdomain=subdomain)
                request.vendor = subdomain_obj.vendor
            except Subdomain.DoesNotExist:
                request.vendor = None
        else:
            request.vendor = None