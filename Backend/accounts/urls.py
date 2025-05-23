from django.urls import path
from . import views

app_name = 'accounts'


urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('register/', views.register, name='register'),
    path('verify-otp/<str:email>/', views.verify_otp, name='verify_otp'),
    path('login/', views.login_vendor, name='login'),
    # path('home/', views.home, name='home'),
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
    
    
    # Customer endpoints:
    path('<str:subdomain>.platform/customer/register/', views.customer_register, name='customer_register'),
    path('<str:subdomain>.platform/customer/verify-otp/', views.verify_customer_otp, name='verify_customer_otp'),
    path('<str:subdomain>.platform/customer/login/', views.customer_login, name='customer_login'),
    # path('<str:subdomain>.platform/customer/forgot-password/', views.customer_forgot_password, name='customer_forgot_password'),
   
     path('<str:subdomain>.platform/customer/forgot-password/', 
         views.customer_forgot_password, 
         name='customer_forgot_password'),
    
     path('<str:subdomain>.platform/customer/verify-reset-otp/<str:email>/',
         views.verify_customer_reset_otp,
         name='verify_customer_reset_otp'),
    
     path('<str:subdomain>.platform/customer/reset-password/<str:email>/',
         views.reset_customer_password,
         name='reset_customer_password'),
    
     path('<str:subdomain>.platform/customer/resend-otp/<str:email>/',
         views.resend_customer_otp,
         name='resend_customer_otp'),
        
     path('<str:subdomain>.platform/customer/logout/', 
         views.customer_logout, 
         name='customer_logout'),  
   
     path('<str:subdomain>.platform/customer/customer-profile/', 
          views.customer_profile, 
          name='customer_profile'),
     
     
     path('<str:subdomain>.platform/customer/dashboard/', 
         views.customer_dashboard, 
         name='customer_dashboard'),
     
     path('vendor/orders/', views.vendor_orders, name='vendor_orders'),
     path('api/orders/<str:order_id>/update-status/', 
         views.update_order_status, 
         name='update_order_status'),
     path('vendor/orders/<int:order_id>/', views.order_detail, name='order_detail'),
     
    path('api/notifications/mark-as-read/', views.mark_notifications_as_read, name='mark_notifications_as_read'),
    path('api/notifications/', views.get_notifications_context, name='get_notifications_api'),
    path('api/notifications/<int:notification_id>/mark-read/', 
         views.mark_single_notification_as_read, 
         name='mark_single_notification_as_read'),
    
    path('dashboard/', views.vendor_dashboard, name='vendor_dashboard'),

    path('home/subdomain/', views.subdomain_management, name='subdomain_management'),
    
    # Add these paths to your urlpatterns
    path('subscription/plans/', views.subscription_plans, name='subscription_plans'),
    # Add these to accounts/urls.py
    # Remove any duplicate URLs and make sure you only have these three for payment
    # IMPORTANT: Remove any duplicate path entries and keep only these three for subscription payment
    path('esewa/subscription/payment/<int:plan_id>/', views.subscription_esewa_payment, name='subscription_esewa_payment'),
    path('esewa/subscription/success/', views.subscription_payment_success, name='subscription_payment_success'),
    path('esewa/subscription/failure/', views.subscription_payment_failure, name='subscription_payment_failure'),
    path('dashboard/subscription/', views.vendor_subscription_tab, name='vendor_subscription_tab'),
    # In urls.py

# Add these paths to your urlpatterns

  path(
    '<str:subdomain>.platform/vendor/reviews/',
    views.vendor_reviews,
    name='vendor_reviews'
  ),
  path(
    '<str:subdomain>.platform/vendor/reviews/reply/<int:review_id>/',
    views.vendor_reply,
    name='vendor_reply'
  ),
   
    path("home/delete-account/", views.vendor_delete_account,
         name="vendor_delete_account"),

    # Customer
    path("<str:subdomain>.platform/customer/delete-account/",
         views.customer_delete_account,
         name="customer_delete_account"), 
    

    path('subscription/start-trial/', views.start_trial, name='start_trial'),
]

    # path('home/products/<int:product_id>/add-color/', views.add_product_color, name='add_product_color'),
    # path('home/products/<int:product_id>/add-size/', views.add_product_size, name='add_product_size'),




