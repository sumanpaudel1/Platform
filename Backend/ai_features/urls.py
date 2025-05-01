from django.urls import path
from . import views
from . import viton_controller
from django.conf import settings
app_name = 'ai_features'

urlpatterns = [
    path('<str:subdomain>/image-search/', views.image_search_view, name='image_search'),
    path('<str:subdomain>/similar-products/<int:product_id>/', views.similar_products_view, name='similar_products'),
    path('<str:subdomain>/index-products/', views.index_products_view, name='index_products'),
    path('<str:subdomain>/index-all-products/', views.index_all_products_view, name='index_all_products'),
    path('<str:subdomain>/test-recommendations/<int:product_id>/', views.test_recommendations, name='test_recommendations'),

    path('try-on-direct/', viton_controller.try_on_direct, name='try_on_direct'),
    path('process-try-on/', viton_controller.process_try_on, name='process_try_on'),
    path('test-image-path/', viton_controller.test_image_path, name='test_image_path'),
    path('proxy-try-on/', views.proxy_try_on, name='proxy_try_on'),

]
if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)