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
    list_filter = ('vendor',)

    def subdomain_url(self, obj):
        if obj and obj.subdomain:
            return format_html(
                '<a href="http://127.0.0.1:8080/{}.platform/home" target="_blank">{}.platform</a>', 
                obj.subdomain, 
                obj.subdomain
            )
        return "No subdomain set"
    subdomain_url.short_description = 'Subdomain URL'
    
    def get_queryset(self, request):
        # Always refresh from DB to ensure latest data
        queryset = super().get_queryset(request).select_related('vendor')
        return queryset

admin.site.register(Vendor, VendorAdmin)
admin.site.register(Subdomain, SubdomainAdmin)

from django.contrib import admin
from .models import VendorSetting, CoverPhoto

class CoverPhotoInline(admin.TabularInline):
    model = CoverPhoto
    extra = 1
    ordering = ['order']




@admin.register(CoverPhoto)
class CoverPhotoAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'created_at']
    ordering = ['order']
    
    
    
from django.contrib import admin
from .models import Vendor, VendorProfile, Notification, VendorSetting

class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ['vendor', 'business_name', 'profile_status', 'is_verified']
    list_filter = ['profile_status', 'is_verified']
    search_fields = ['vendor__email', 'business_name', 'pan_vat_number']
    actions = ['approve_profiles', 'reject_profiles']
    
    def approve_profiles(self, request, queryset):
        from django.utils import timezone
        
        for profile in queryset:
            profile.profile_status = 'approved'
            profile.is_verified = True
            profile.verification_date = timezone.now()
            profile.verified_by = request.user if hasattr(request.user, 'id') else None
            profile.save()
            
            # Create notification for vendor
            Notification.objects.create(
                vendor=profile.vendor,
                message=f"Your business profile for {profile.business_name} has been approved. You can now set up your subdomain.",
                notification_type='profile_update',
                action_url='/home/subdomain/'  # Add this line to redirect to the subdomain management page
            )
        
        self.message_user(request, f"{queryset.count()} profiles have been approved successfully.")
    
    def reject_profiles(self, request, queryset):
        for profile in queryset:
            profile.profile_status = 'rejected'
            profile.is_verified = False
            profile.save()
            
            # Create notification for vendor
            Notification.objects.create(
                vendor=profile.vendor,
                message=f"Your business profile for {profile.business_name} has been rejected. Please update your information.",
                notification_type='profile_update'
            )
        
        self.message_user(request, f"{queryset.count()} profiles have been rejected.")
    
    approve_profiles.short_description = "Approve selected vendor profiles"
    reject_profiles.short_description = "Reject selected vendor profiles"

class NotificationAdmin(admin.ModelAdmin):
    list_display = ['message', 'vendor', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read']
    search_fields = ['message', 'vendor__email']
    
    
    
# Update VendorSettingAdmin to include subdomain management
@admin.register(VendorSetting)
class VendorSettingAdmin(admin.ModelAdmin):
    list_display = ['vendor', 'store_name', 'subdomain', 'is_subdomain_active', 'subdomain_request_date']
    list_filter = ['is_subdomain_active']
    search_fields = ['vendor__email', 'subdomain', 'store_name']
    actions = ['approve_subdomains', 'reject_subdomains']
    
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
           
         
        ('Subdomain Settings', {
            'fields': ('subdomain', 'is_subdomain_active', 'subdomain_request_date', 'subdomain_approval_date'),
        }),
    )
    
    def approve_subdomains(self, request, queryset):
        from django.utils import timezone
        from .models import Subdomain
        count = 0
        
        for vendor_setting in queryset:
            # Print debug information
            print(f"Processing vendor setting: {vendor_setting.id}, Subdomain: {vendor_setting.subdomain}, Active: {vendor_setting.is_subdomain_active}")
            
            if vendor_setting.subdomain:  # Remove the active check to force update
                # Update VendorSetting
                vendor_setting.is_subdomain_active = True
                vendor_setting.subdomain_approval_date = timezone.now()
                vendor_setting.save()
                
                # Force update Subdomain record with transaction to ensure atomicity
                from django.db import transaction
                with transaction.atomic():
                    # Remove any existing subdomain first
                    Subdomain.objects.filter(vendor=vendor_setting.vendor).delete()
                    
                    # Create new subdomain
                    subdomain_obj = Subdomain.objects.create(
                        vendor=vendor_setting.vendor,
                        subdomain=vendor_setting.subdomain
                    )
                    print(f"Created subdomain: {subdomain_obj.id} - {subdomain_obj.subdomain}")
                
                # Create notification
                Notification.objects.create(
                    vendor=vendor_setting.vendor,
                    message=f"Your subdomain request '{vendor_setting.subdomain}.platform' has been approved!",
                    notification_type='subdomain_update',
                    action_url='/home/subdomain/',
                    related_vendor_id=vendor_setting.vendor.id
                )
                count += 1
        
        self.message_user(request, f"{count} subdomain requests were approved successfully.")
    
    def reject_subdomains(self, request, queryset):
        from .models import Subdomain
        count = 0
        
        for vendor_setting in queryset:
            if vendor_setting.subdomain and not vendor_setting.is_subdomain_active:
                old_subdomain = vendor_setting.subdomain
                
                # Create notification
                Notification.objects.create(
                    vendor=vendor_setting.vendor,
                    message=f"Your subdomain request '{old_subdomain}.platform' was rejected. Please choose another name.",
                    notification_type='subdomain_update',
                    action_url='/home/subdomain/'
                )
                
                # Remove Subdomain record if exists
                Subdomain.objects.filter(vendor=vendor_setting.vendor).delete()
                
                # Reset subdomain
                vendor_setting.subdomain = None
                vendor_setting.save()
                count += 1
        
        self.message_user(request, f"{count} subdomain requests were rejected.")


            
            
    approve_subdomains.short_description = "Approve selected subdomain requests"
    reject_subdomains.short_description = "Reject selected subdomain requests"

# Register models with custom admin classes
admin.site.register(VendorProfile, VendorProfileAdmin)
admin.site.register(Notification, NotificationAdmin)


from .models import CollectionImage

@admin.register(CollectionImage)
class CollectionImageAdmin(admin.ModelAdmin):
    list_display = ['vendor_setting', 'collection_type', 'created_at']
    list_filter = ['collection_type']
    search_fields = ['vendor_setting__vendor__email', 'title', 'subtitle']

