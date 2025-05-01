"""
URL configuration for Backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from products import views
from django.conf import settings
from django.conf.urls.static import static
from products import views as products_views  # Fixed import name
from accounts import views as accounts_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('accounts/', include('allauth.urls')),
    path('', include('products.urls', namespace='products')),
    path('', include('ai_features.urls', namespace='ai_features')),
    
        path('esewa/success/', include([
        path('', accounts_views.subscription_payment_success, name='subscription_success'),
        path('', products_views.esewa_payment_success, name='product_success'),
    ])),
    path('esewa/failure/', include([
        path('', accounts_views.subscription_payment_failure, name='subscription_failure'),
        path('', products_views.esewa_payment_failure, name='product_failure'),
    ])),
    
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
