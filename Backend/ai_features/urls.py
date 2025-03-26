from django.urls import path
from . import views

app_name = 'ai_features'

urlpatterns = [
    path('<str:subdomain>/image-search/', views.image_search_view, name='image_search'),
    path('<str:subdomain>/similar-products/<int:product_id>/', views.similar_products_view, name='similar_products'),
    path('<str:subdomain>/index-products/', views.index_products_view, name='index_products'),
    path('<str:subdomain>/index-all-products/', views.index_all_products_view, name='index_all_products'),
    path('<str:subdomain>/test-recommendations/<int:product_id>/', views.test_recommendations, name='test_recommendations'),

]