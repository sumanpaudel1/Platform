from django.urls import path
from .views import vendor_home, product_detail,  product_create, wishlist_view, add_to_wishlist, remove_from_wishlist, add_to_cart, update_cart, remove_from_cart, cart_view, toggle_wishlist
app_name = 'products'


urlpatterns = [
    path('<str:subdomain>.platform/home/', vendor_home, name='vendor_home'),
    path('<str:subdomain>.platform/product/<slug:slug>/', product_detail, name='product_detail'),
    path('product/new/', product_create, name='product_create'),
    
    
    path('<str:subdomain>.platform/cart/', cart_view, name='cart'),
    path('add-to-cart/', add_to_cart, name='add_to_cart'), 
    path('api/cart/update/', update_cart, name='update_cart'),
    path('api/cart/remove/<int:item_id>/',remove_from_cart, name='remove_from_cart'),
    
    path('<str:subdomain>.platform/wishlist/', wishlist_view, name='wishlist'),
    path('api/wishlist/add/', add_to_wishlist, name='add_to_wishlist'),
    path('api/wishlist/remove/<int:product_id>/', remove_from_wishlist, name='remove_from_wishlist'),
    path('api/wishlist/toggle/', toggle_wishlist, name='toggle_wishlist'),
    

]