from django.urls import path
from .views import vendor_home, product_detail,  product_create, wishlist_view, add_to_cart, update_cart, remove_from_cart, cart_view, toggle_wishlist
from . import views
from django.conf import settings
from django.conf.urls.static import static

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
    path('api/wishlist/toggle/', toggle_wishlist, name='toggle_wishlist'),
    
    
    path('<str:subdomain>.platform/checkout/', views.checkout_view, name='checkout'),
    path('<str:subdomain>.platform/api/orders/place/', 
         views.place_order, 
         name='place_order'),
    path('esewa/payment/<str:order_id>/', views.initiate_esewa_payment, name='esewa_payment'),
    path('esewa/success/', views.esewa_payment_success, name='esewa_success'),
    path('esewa/failure/', views.esewa_payment_failure, name='esewa_failure'),
    path('<str:subdomain>.platform/order/confirmation/<str:order_id>/', 
         views.order_confirmation, 
         name='order_confirmation'),

    
    path('<str:subdomain>.platform/orders/', 
         views.orders_list, 
         name='orders'),
    
    path('<str:subdomain>.platform/order/<str:order_id>/', 
         views.order_detail, 
         name='order_detail'),
    
    path('api/orders/<str:order_id>/cancel/',
         views.cancel_order,
         name='cancel_order'),
         
    path('api/orders/<str:order_id>/delete/',
         views.delete_order,
         name='delete_order'),
    
   
     path('<str:subdomain>.platform/search/',
          views.search_products,
           name='search'),

     path('<str:subdomain>/products/', views.product_list, name='product_list'),

     path('<str:subdomain>.platform/image-search/', 
         views.image_search_view, 
         name='image_search'),
     
     path('<str:subdomain>.platform/buy-now-checkout/', views.buy_now_checkout, name='buy_now_checkout'),
     
     path('api/store-buy-now/', views.store_buy_now_data, name='store_buy_now_data'),
     
     path('api/orders/<str:order_id>/payment-details/', views.get_payment_details, name='order_payment_details'),
     path('try-on-redirect/', views.try_on_redirect, name='try_on_redirect'),
     path(
     '<str:subdomain>.platform/review/<str:order_id>/<int:product_id>/',
     views.submit_review,
     name='submit_review'
     ),
     
#      path('<str:subdomain>/debug-pinecone/', views.debug_pinecone, name='debug_pinecone'),
#      # Add this line right after the debug-pinecone URL
#    path('<str:subdomain>/debug-category/', views.debug_category, name='debug_category'),



]