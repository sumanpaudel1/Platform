from django import template
from products.models import Category

register = template.Library()

@register.filter
def filter_by_id(categories, id_value):
    """Get category name by ID from a QuerySet of categories"""
    for category in categories:
        if str(category.id) == str(id_value):
            return category.category_name
    return "Unknown Category"