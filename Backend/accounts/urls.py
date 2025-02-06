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
]