from django.urls import path
from . import views

urlpatterns = [
    
    path('register/', views.register, name='register'),
    path('verify-otp/<str:email>/', views.verify_otp, name='verify_otp'),
    path('login/', views.login_vendor, name='login'),
    path('home/', views.home, name='home'),
    path('logout/', views.logout_vendor, name='logout'), 
    path('resend-otp/<str:email>/', views.resend_otp, name='resend_otp'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-reset-otp/<str:email>/', views.verify_reset_otp, name='verify_reset_otp'),
    path('reset-password/<str:email>/', views.reset_password, name='reset_password'),
    path('home/profile/', views.vendor_profile, name='vendor_profile'),
    path('home/store-settings/', views.store_settings, name='vendor_settings'),
    path('delete-cover-photo/<int:photo_id>/', views.delete_cover_photo, name='delete_cover_photo'),
    
    
    path('home/products/', views.vendor_products, name='vendor_products'),
    path('home/products/create/', views.vendor_product_create, name='vendor_product_create'),
    path('home/products/<int:pk>/edit/', views.vendor_product_edit, name='vendor_product_edit'),
    path('home/products/<int:pk>/delete/', views.vendor_product_delete, name='vendor_product_delete'),
    path('home/products/add-category/', views.add_category, name='add_category'),
   
   
    path('home/products/images/<int:image_id>/delete/', views.delete_product_image, name='delete_product_image'),
    
    
    path('home/products/add-category/', views.add_category, name='add_category'),
    path('home/products/add-color/', views.add_color_variant, name='add_color_variant'),
    path('home/products/add-size/', views.add_size_variant, name='add_size_variant'),
    path('home/products/images/<int:image_id>/delete/', views.delete_product_image, name='delete_product_image'),
    path('home/products/<int:pk>/add-images/', views.add_product_images, name='add_product_images'),
    path('home/products/category/<int:pk>/delete/', views.delete_category, name='delete_category'),
    path('home/products/color/<int:pk>/delete/', views.delete_color_variant, name='delete_color_variant'),
    path('home/products/size/<int:pk>/delete/', views.delete_size_variant, name='delete_size_variant'),
    path('products/<int:pk>/delete/', views.delete_product, name='delete_product'),
    
]

    # path('home/products/<int:product_id>/add-color/', views.add_product_color, name='add_product_color'),
    # path('home/products/<int:product_id>/add-size/', views.add_product_size, name='add_product_size'),




