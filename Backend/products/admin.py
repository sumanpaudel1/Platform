from django.contrib import admin
from .models import Category, Product, ColorVariant, SizeVariant, ProductImage

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('category_name',)
    search_fields = ('category_name',)
    prepopulated_fields = {'slug': ('category_name',)}

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor', 'category', 'price', 'stock')
    search_fields = ('name', 'vendor__username', 'category__category_name')
    list_filter = ('category', 'vendor')
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ('color_variant', 'size_variant')
    inlines = [ProductImageInline]
    fieldsets = (
        (None, {
            'fields': ('vendor', 'name', 'slug', 'category', 'description')
        }),
        ('Pricing', {
            'fields': ('price', 'cut_price')
        }),
        ('Inventory', {
            'fields': ('stock', 'color_variant', 'size_variant')
        }),
        ('Meta', {
            'fields': ('rating',)
        }),
    )

@admin.register(ColorVariant) 
class ColorVariantAdmin(admin.ModelAdmin):
    list_display = ('color_name',)
    search_fields = ('color_name',)

@admin.register(SizeVariant)
class SizeVariantAdmin(admin.ModelAdmin):
    list_display = ('size_name', 'price')
    search_fields = ('size_name',)