from django.utils.deprecation import MiddlewareMixin
from accounts.models import Subdomain
from django.shortcuts import redirect
from django.contrib import messages

# class VendorMiddleware(MiddlewareMixin):
#     def process_request(self, request):
#         path_parts = request.path.split('/')
#         if len(path_parts) > 1:
#             # Extract subdomain from URL pattern like "subdomain.platform/home"
#             subdomain = path_parts[1].replace('.platform', '')
#             try:
#                 subdomain_obj = Subdomain.objects.get(subdomain=subdomain)
#                 request.vendor = subdomain_obj.vendor
#             except Subdomain.DoesNotExist:
#                 request.vendor = None
#         else:
#             request.vendor = None
            
            

class VendorMiddleware(MiddlewareMixin):
    def process_request(self, request):
        path_parts = request.path.split('/')
        if len(path_parts) > 1:
            # Extract subdomain from URL pattern like "subdomain.platform/home"
            raw_subdomain = path_parts[1]
            if '.platform' in raw_subdomain:
                subdomain = raw_subdomain.replace('.platform', '')
                try:
                    # Add caching to reduce database hits
                    from django.core.cache import cache
                    cache_key = f"subdomain_{subdomain}"
                    subdomain_obj = cache.get(cache_key)
                    
                    if subdomain_obj is None:
                        subdomain_obj = Subdomain.objects.select_related('vendor').get(subdomain=subdomain)
                        cache.set(cache_key, subdomain_obj, 3600)  # Cache for 1 hour
                        
                    request.vendor = subdomain_obj.vendor
                    request.subdomain = subdomain
                    # Store cleaned subdomain to avoid repeated processing
                    request.cleaned_subdomain = subdomain
                except Subdomain.DoesNotExist:
                    request.vendor = None
                    request.subdomain = None
            else:
                request.vendor = None
                request.subdomain = None
        else:
            request.vendor = None
            request.subdomain = None