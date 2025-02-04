from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from datetime import timedelta
from django.utils.timezone import now
from django.utils.text import slugify
import uuid
# Vendor Manager
class VendorManager(BaseUserManager):
    def create_vendor(self, email, phone_number=None, first_name=None, last_name=None, middle_name=None, password=None):
        if not email:
            raise ValueError("Vendors must have an email address")
        vendor = self.model(
            email=self.normalize_email(email),
            phone_number=phone_number,
            first_name=first_name or '',  # Handle social auth where first_name might not be provided
            last_name=last_name or '',    # Handle social auth where last_name might not be provided
            middle_name=middle_name,    # Handle social auth where middle_name might not be provided
            
        )
        if password:
            vendor.set_password(password)
        vendor.save(using=self._db)
        
        # Create and save the subdomain
        unique_id = str(uuid.uuid4())[:8]  # Generate a unique identifier
        subdomain = Subdomain(vendor=vendor, subdomain=slugify(f"{vendor.first_name}-{unique_id}"))
        subdomain.save()
        
        return vendor

    def create_supervendor(self, email, phone_number, first_name, last_name, middle_name, password):
        vendor = self.create_vendor(email, phone_number, first_name, last_name, middle_name, password)
        vendor.is_admin = True
        vendor.is_staff = True
        vendor.save(using=self._db)
        return vendor

# Vendor Model
class Vendor(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True, unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    middle_name = models.CharField(max_length=30, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    
    objects = VendorManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'phone_number']
    
    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    @property   
    def is_staff(self):
        return self.is_admin

    def __str__(self):
        return self.email

# OTP Model
class OTP(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('used', 'Used'),
        ('expired', 'Expired')
    ]
    
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    
    def is_valid(self, entered_otp):
        # Check if OTP is active and matches the entered value
        if self.status != 'active':
            print("OTP status is not active.")
            return False
        if self.is_expired():
            print("OTP has expired.")
            return False
        if str(self.otp) != str(entered_otp):
            print("Entered OTP does not match.")
            return False
        return True

    
    def is_expired(self):
        expiry_time = self.created_at + timedelta(minutes=1.5)
        if now() > expiry_time:
            if self.status != 'expired':
                self.status = 'expired'
                self.save(update_fields=['status'])  # Save only the status field
            return True
        return False
    
    def mark_as_used(self):
        self.status = 'used'
        self.save()
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.email} - {self.status}"
    
    
    

class Subdomain(models.Model):
    vendor = models.OneToOneField(Vendor, on_delete=models.CASCADE)
    subdomain = models.CharField(max_length=50, unique=True)

    def save(self, *args, **kwargs):
        if not self.subdomain:
            self.subdomain = slugify(f"{self.vendor.first_name}-{str(uuid.uuid4())[:8]}")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.subdomain
    


from django.db import models
from django.contrib.auth.models import User
from colorfield.fields import ColorField

class CoverPhoto(models.Model):
    vendor_setting = models.ForeignKey('VendorSetting', on_delete=models.CASCADE, related_name='cover_photos')
    image = models.ImageField(upload_to='vendor/covers/')
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Cover Photo {self.order}"

class VendorSetting(models.Model):
    vendor = models.OneToOneField(Vendor, on_delete=models.CASCADE, related_name='settings')
    logo = models.ImageField(upload_to='vendor/logos/', null=True, blank=True)
    favicon = models.ImageField(upload_to='vendor/favicons/', null=True, blank=True)
    announcement = models.CharField(max_length=200, blank=True, null=True)

    
    # Colors
    primary_color = ColorField(default='#007bff')
    secondary_color = ColorField(default='#6c757d')
    accent_color = ColorField(default='#28a745')
    
    # Typography
    FONT_CHOICES = [
        ('Roboto', 'Roboto'),
        ('Open Sans', 'Open Sans'),
        ('Lato', 'Lato'),
        ('Poppins', 'Poppins'),
        ('Montserrat', 'Montserrat'),
    ]
    heading_font = models.CharField(max_length=50, choices=FONT_CHOICES, default='Roboto')
    body_font = models.CharField(max_length=50, choices=FONT_CHOICES, default='Open Sans')
    
    # Store Settings
    store_name = models.CharField(max_length=100)
    tagline = models.CharField(max_length=200, blank=True)
    about = models.TextField(blank=True)
    
    # Popup Settings
    popup_image = models.ImageField(upload_to='vendor/popups/', null=True, blank=True)
    popup_title = models.CharField(max_length=100, blank=True)
    popup_text = models.TextField(blank=True)
    show_popup = models.BooleanField(default=False)
    popup_delay = models.IntegerField(default=3, help_text="Delay in seconds before showing popup")
    
    # Social Links
    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    twitter = models.URLField(blank=True)
    
    # Contact Information
    contact_email = models.EmailField(blank=True, null=True, help_text="Support email address")
    contact_phone = models.CharField(max_length=20, blank=True, null=True, help_text="Support phone number")
    contact_address = models.CharField(max_length=200, blank=True, null=True, help_text="Physical address")
    
    # SEO
    meta_title = models.CharField(max_length=100, blank=True)
    meta_description = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Vendor Setting"
        verbose_name_plural = "Vendor Settings"

    def __str__(self):
        return f"Settings for {self.vendor.first_name}"