from django.db import models
from products.models import Product
from accounts.models import Vendor

class SearchQuery(models.Model):
    """Stores search queries and results for analytics"""
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    query_text = models.TextField(null=True, blank=True)
    is_image_search = models.BooleanField(default=False)
    result_count = models.IntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        if self.is_image_search:
            return f"Image search ({self.result_count} results)"
        return f"Text search: {self.query_text[:30]} ({self.result_count} results)"

class SearchResult(models.Model):
    """Stores individual search results"""
    search_query = models.ForeignKey(SearchQuery, on_delete=models.CASCADE, related_name='results')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    similarity_score = models.FloatField()
    position = models.IntegerField()
    
    class Meta:
        ordering = ['position']
        
    def __str__(self):
        return f"Result: {self.product.name} ({self.similarity_score:.2f})"
        
class RecommendationEvent(models.Model):
    """Tracks when recommendations are shown to users"""
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    source_product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='source_recommendations')
    recommended_product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='as_recommendation')
    recommendation_type = models.CharField(max_length=50, choices=[
        ('detail_page', 'Detail Page'),
        ('home_page', 'Home Page'),
    ])
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.source_product.name} → {self.recommended_product.name}"