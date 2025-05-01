from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin , Group, Permission
from datetime import timedelta
from django.utils.timezone import now
from django.utils.text import slugify
import uuid
from django.utils import timezone
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
    
    
    groups = models.ManyToManyField(
        Group,
        related_name="vendor_users",  # unique related_name for Vendor
        blank=True,
        help_text="The groups this vendor belongs to.",
        verbose_name="groups"
    )
    
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="vendor_permissions",  # unique related_name for Vendor
        blank=True,
        help_text="Specific permissions for this vendor.",
        verbose_name="user permissions"
    )
    
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
        # Make sure subdomain is clean before saving
        if self.subdomain:
            # Remove all invalid characters, keep only lowercase letters, numbers, and hyphens
            import re
            self.subdomain = re.sub(r'[^a-z0-9-]', '', self.subdomain.lower())
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.subdomain}"
    


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
    
    # Profile Status
    is_profile_complete = models.BooleanField(default=False)
    profile_completion_date = models.DateTimeField(null=True, blank=True)
    
    # Subdomain Management
    subdomain = models.CharField(max_length=50, unique=True, null=True, blank=True)
    is_subdomain_active = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    subdomain_request_date = models.DateTimeField(null=True, blank=True)
    subdomain_approval_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Vendor Setting"
        verbose_name_plural = "Vendor Settings"
        
    def save(self, *args, **kwargs):
        # Handle subdomain changes
        if self.subdomain and not self.subdomain_request_date:
            self.subdomain_request_date = timezone.now()
            
        super().save(*args, **kwargs)
        
        # Keep Subdomain model in sync
        if self.is_subdomain_active and self.subdomain:
            from django.db import transaction
            with transaction.atomic():
                Subdomain.objects.update_or_create(
                    vendor=self.vendor,
                    defaults={'subdomain': self.subdomain}
                )
        elif not self.is_subdomain_active or not self.subdomain:
            # Remove subdomain record if subdomain is deactivated or removed
            Subdomain.objects.filter(vendor=self.vendor).delete()

    def __str__(self):
        return f"Settings for {self.vendor.first_name}"

    def request_subdomain(self, subdomain_name):
        self.subdomain = subdomain_name
        self.subdomain_request_date = timezone.now()
        self.save()

    def approve_subdomain(self):
        self.is_subdomain_active = True
        self.subdomain_approval_date = timezone.now()
        self.save()
        
        
      
      
      

def vendor_photo_path(instance, filename):
    return f'vendor_photos/{instance.vendor.id}/{filename}'

def vendor_document_path(instance, filename):
    return f'vendor_documents/{instance.vendor.id}/{filename}'


class StorePhoto(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    image = models.ImageField(upload_to=vendor_photo_path)
    caption = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts_storephoto'
        ordering = ['-is_primary', '-uploaded_at']

class VendorProfile(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ]

    # Basic Information
    vendor = models.OneToOneField(Vendor, on_delete=models.CASCADE, related_name='profile')
    profile_photo = models.ImageField(
        upload_to=vendor_photo_path,
        null=True,
        blank=True
    )
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')])
    
    # Business Information
    business_name = models.CharField(max_length=100)
    business_type = models.CharField(max_length=50)
    pan_vat_number = models.CharField(max_length=50, unique=True)
    registration_number = models.CharField(max_length=50, unique=True)
    
    # Address Information
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    country = models.CharField(max_length=100)
    
    # Contact Information
    alternate_phone = models.CharField(max_length=15, blank=True)
    alternate_email = models.EmailField(blank=True)
    
    # Document Uploads
    pan_vat_document = models.FileField(upload_to=vendor_document_path)
    business_registration = models.FileField(upload_to=vendor_document_path)
    citizenship_front = models.ImageField(upload_to=vendor_document_path)
    citizenship_back = models.ImageField(upload_to=vendor_document_path)
    citizenship_number = models.CharField(max_length=50, unique=True)
    
    # Store/Warehouse Photos
    # store_photos = models.ManyToManyField(StorePhoto, blank=True)
    # Status and Verification
    profile_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_verified = models.BooleanField(default=False)
    verification_date = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        Vendor, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='verified_profiles'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'accounts_vendorprofile'

    def __str__(self):
        return f"Profile of {self.vendor.first_name} {self.vendor.last_name}"


    def is_profile_complete(self):
        """Check if all required profile fields are filled"""
        # Check required text fields
        required_text_fields = [
            'business_name', 
            'business_type', 
            'pan_vat_number',
            'registration_number',
            'street_address',
            'city',
            'state', 
            'postal_code',
            'country',
            'citizenship_number'
        ]
        
        for field in required_text_fields:
            if not getattr(self, field, None):
                return False
                
        # Check required file fields
        if not self.pan_vat_document or not self.pan_vat_document.name:
            return False
        if not self.business_registration or not self.business_registration.name:
            return False
        if not self.citizenship_front or not self.citizenship_front.name:
            return False
        if not self.citizenship_back or not self.citizenship_back.name:
            return False
                
        return True








# Customer Manager
class CustomerManager(BaseUserManager):
    def create_customer(self, email, phone_number=None, first_name=None, last_name=None, password=None, vendor=None):
        if not email:
            raise ValueError("Customers must have an email address")
        if vendor is None:
            raise ValueError("Customer registration must occur on a vendor subdomain")
        
        # Check if customer already exists for this vendor
        if self.filter(email=email, vendor=vendor).exists():
            raise ValueError("You are already registered with this store")
        
        
        customer = self.model(
            email=self.normalize_email(email),
            phone_number=phone_number,
            first_name=first_name or '',
            last_name=last_name or '',
            vendor=vendor
        )
        if password:
            customer.set_password(password)
        customer.save(using=self._db)
        return customer
    
    def get_by_natural_key(self, email):
        return self.get(email=email)

# Customer Model
class Customer(AbstractBaseUser, PermissionsMixin):
    
    profile_picture = models.ImageField(
        upload_to='customer_profiles/',
        null=True,
        blank=True
    )
    email = models.EmailField()
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    # Associate each customer with a Vendor.
    vendor = models.ForeignKey('Vendor', on_delete=models.CASCADE, related_name='customers')
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = CustomerManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    
    groups = models.ManyToManyField(
        Group,
        related_name="customer_users",  # unique related_name for Customer
        blank=True,
        help_text="The groups this user belongs to.",
        verbose_name="groups"
    )
    
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="customer_permissions",  # unique related_name for Customer
        blank=True,
        help_text="Specific permissions for this user.",
        verbose_name="user permissions"
    )

    def __str__(self):
        return self.email
    
    class Meta:
        unique_together = ['email', 'vendor']  # This ensures email uniqueness per vendor
        constraints = [
            models.UniqueConstraint(
                fields=['email', 'vendor'], 
                name='unique_customer_email_per_vendor'
            )
        ]
        



class Notification(models.Model):
    # Existing fields
    message = models.CharField(max_length=255)
    vendor = models.ForeignKey('Vendor', on_delete=models.CASCADE, null=True, blank=True)  # Now nullable
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    order_id = models.CharField(max_length=50, blank=True, null=True)
    
    # New fields
    is_admin = models.BooleanField(default=False)  # True for admin notifications
    notification_type = models.CharField(max_length=50, default='general',
        choices=[
            ('general', 'General Notification'),
            ('order', 'Order Notification'),
            ('subdomain_request', 'Subdomain Request'),
            ('subdomain_update', 'Subdomain Update'),
            ('profile_update', 'Profile Update'),
        ]
    )
    
    # Related fields for subdomain approval
    related_vendor_id = models.IntegerField(null=True, blank=True)  # Store vendor ID for admin actions
    action_url = models.CharField(max_length=255, null=True, blank=True)  # URL for action button

    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Notification for {self.vendor}: {self.message[:30]}"
    
    
    


class CollectionImage(models.Model):
    COLLECTION_CHOICES = [
        ('new_arrivals', 'New Arrivals'),
        ('best_sellers', 'Best Sellers'), 
        ('season_special', 'Season Special'),
    ]
    
    vendor_setting = models.ForeignKey('VendorSetting', on_delete=models.CASCADE, related_name='collection_images')
    collection_type = models.CharField(max_length=20, choices=COLLECTION_CHOICES)
    image = models.ImageField(upload_to='vendor/collections/')
    title = models.CharField(max_length=100, default="New Arrivals")
    subtitle = models.CharField(max_length=200, default="Latest styles for you")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['vendor_setting', 'collection_type']
        
    def __str__(self):
        return f"{self.get_collection_type_display()} for {self.vendor_setting.vendor}"
    
    
    



from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
import uuid

# Add these to your existing models.py file

# Find your SubscriptionPlan model and update it:
class SubscriptionPlan(models.Model):
    """Model to store subscription plan details"""
    PERIOD_CHOICES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annual', 'Annual'),
    ]
    
    PLAN_TYPE_CHOICES = [
        ('free', 'Free'),
        ('starter', 'Starter'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    ]
    
    name = models.CharField(max_length=100)  # Professional, Enterprise
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPE_CHOICES, default='starter')
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    max_products = models.IntegerField(default=10)
    transaction_fee_percent = models.DecimalField(max_digits=4, decimal_places=2, default=5.00)
    
    # Additional fields
    description = models.TextField(blank=True)
    has_analytics = models.BooleanField(default=False)
    has_ai_recommendations = models.BooleanField(default=False)
    custom_domain = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['plan_type', 'period']
    
    def __str__(self):
        return f"{self.name} ({self.get_period_display()}) - ${self.price}"


class Subscription(models.Model):
    """Model to track vendor subscriptions"""
    STATUS_CHOICES = [
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('expired', 'Expired'),
    ]
    
    vendor = models.OneToOneField('Vendor', on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='trial')
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    trial_end_date = models.DateTimeField(null=True, blank=True)
    is_trial = models.BooleanField(default=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    auto_renew = models.BooleanField(default=False)
    subscription_id = models.CharField(max_length=50, default=uuid.uuid4, unique=True)
    last_payment_date = models.DateTimeField(null=True, blank=True)
    next_payment_date = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.vendor.email} - {self.get_status_display}"
    
    def save(self, *args, **kwargs):
        # Set trial end date if not set
        if self.is_trial and not self.trial_end_date:
            self.trial_end_date = timezone.now() + timezone.timedelta(days=10)
            self.end_date = self.trial_end_date
            
        # Set end date based on plan period if not trial
        if not self.is_trial and self.plan and not self.id:  # Only on create, not update
            if self.plan.period == 'monthly':
                self.end_date = self.start_date + timezone.timedelta(days=30)
            elif self.plan.period == 'quarterly':
                self.end_date = self.start_date + timezone.timedelta(days=90)
            elif self.plan.period == 'annual':
                self.end_date = self.start_date + timezone.timedelta(days=365)
                
        super().save(*args, **kwargs)
        
    # Add these methods to your Subscription model
    @property
    def days_remaining(self):
        """Return the number of days remaining in the subscription"""
        now = timezone.now()
        if self.end_date > now:
            return (self.end_date - now).days
        return 0

    @property
    def get_status_display(self):
        """Return a display-friendly status"""
        status_map = {
            'trial': 'Free Trial',
            'active': 'Active',
            'past_due': 'Past Due',
            'canceled': 'Canceled',
            'expired': 'Expired'
        }
        return status_map.get(self.status, self.status.title())
    
    
    @property
    def is_active(self):
        """Check if subscription is active"""
        return self.status in ['trial', 'active'] and timezone.now() < self.end_date
    
    def get_product_limit(self):
        """Get product limit based on plan or trial"""
        if self.is_trial:
            return 10  # Trial product limit
        return self.plan.product_limit if self.plan else 0


class SubscriptionPayment(models.Model):
    """Model to track subscription payments"""
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=255)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=50, default='esewa')
    status = models.CharField(max_length=20, default='completed')
    response_data = models.JSONField(null=True, blank=True)
    
    def __str__(self):
        return f"Payment of ${self.amount} for {self.subscription.vendor.email}"
