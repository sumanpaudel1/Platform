from django.contrib import admin
from django.utils.html import format_html
from .models import Vendor, Subdomain

class VendorAdmin(admin.ModelAdmin):
    list_display = ('vendor_name', 'email', 'phone_number', 'is_verified', 'is_active', 'is_admin')
    search_fields = ('first_name', 'last_name', 'email')
    list_filter = ('is_verified', 'is_active', 'is_admin')
    fields = ('email', 'first_name', 'last_name', 'middle_name', 'is_active', 'is_verified', 'is_admin')

    def vendor_name(self, obj):
        return f"{obj.first_name} {obj.middle_name or ''} {obj.last_name}"
    vendor_name.short_description = 'Vendor Name'

    def view_products(self, obj):
        return format_html("<a href='/admin/products/product/?vendor__id__exact={}'>View Products</a>", obj.id)
    view_products.allow_tags = True
    view_products.short_description = 'Products'

class SubdomainAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'subdomain', 'subdomain_url')
    search_fields = ('subdomain', 'vendor__first_name', 'vendor__last_name', 'vendor__email')

    def subdomain_url(self, obj):
        return format_html(
            '<a href="http://127.0.0.1:8080/{}.platform/home" target="_blank">http://127.0.0.1:8080/{}.platform/home</a>', 
            obj.subdomain, 
            obj.subdomain
        )
    subdomain_url.short_description = 'Subdomain URL'

admin.site.register(Vendor, VendorAdmin)
admin.site.register(Subdomain, SubdomainAdmin)

from django.contrib import admin
from .models import VendorSetting, CoverPhoto

class CoverPhotoInline(admin.TabularInline):
    model = CoverPhoto
    extra = 1
    ordering = ['order']

@admin.register(VendorSetting)
class VendorSettingAdmin(admin.ModelAdmin):
    inlines = [CoverPhotoInline]
    fieldsets = (
        ('Branding', {
            'fields': ('vendor', 'logo', 'favicon')
        }),
        ('Colors', {
            'fields': ('primary_color', 'secondary_color', 'accent_color')
        }),
        ('Typography', {
            'fields': ('heading_font', 'body_font')
        }),
        ('Store Info', {
            'fields': ('store_name', 'tagline', 'about','announcement' )
        }),
        ('Social Links', {
            'fields': ('facebook', 'instagram', 'twitter')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description')
        }),
        
        ('Contact Information', {
            'fields': ('contact_email', 'contact_phone', 'contact_address'),
            'classes': ('wide',),
        }),
        
        ('Popup Settings', {
            'fields': ('popup_image', 'popup_title', 'popup_text', 'show_popup', 'popup_delay'),
            'classes': ('collapse',),
        }),
    )

@admin.register(CoverPhoto)
class CoverPhotoAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'created_at']
    ordering = ['order']