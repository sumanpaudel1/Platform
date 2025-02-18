from django.urls import path
from .views import vendor_home, product_detail, product_create
app_name = 'products'


urlpatterns = [
    path('<str:subdomain>.platform/home/', vendor_home, name='vendor_home'),
    path('<str:subdomain>.platform/product/<slug:slug>/', product_detail, name='product_detail'),
    path('product/new/', product_create, name='product_create'),

]