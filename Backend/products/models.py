from django.db import models
from accounts.models import Vendor
from django.utils.text import slugify

class Category(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='categories')
    category_name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, null=True, blank=True)
    category_image = models.ImageField(upload_to="categories")

    class Meta:
        verbose_name_plural = "Categories"
        unique_together = ['vendor', 'category_name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.category_name)
        super(Category, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.category_name} - {self.vendor.first_name}"

class ColorVariant(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='colors')
    # Changed related_name to avoid conflict
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='product_colors', null=True)
    color_name = models.CharField(max_length=100)
    image = models.ImageField(upload_to="color_variants", blank=True, null=True)

    class Meta:
        unique_together = ['vendor', 'product', 'color_name']

    def __str__(self):
        return f"{self.color_name} - {self.product.name if self.product else 'No Product'}"

class SizeVariant(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='sizes')
    # Changed related_name to avoid conflict
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='product_sizes', null=True)
    size_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ['vendor', 'size_name', 'product']

    def __str__(self):
        return f"{self.size_name} - {self.product.name if self.product else 'No Product'}"


class Product(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="products")
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cut_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.IntegerField()
    rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    color_variant = models.ManyToManyField(ColorVariant, blank=True, related_name='variant_products')
    size_variant = models.ManyToManyField(SizeVariant, blank=True, related_name='variant_products')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        is_new = self._state.adding
        super(Product, self).save(*args, **kwargs)
        
        
        if is_new:
            # For new products, don't index yet (images will be added after)
            pass
        elif self.product_images.exists():
            try:
                from ai_features.clip_pineconesearch import CLIPPineconeSearch
                clip_search = CLIPPineconeSearch()
                clip_search.index_product(self)
                print(f"Product {self.id} automatically indexed for image search")
            except Exception as e:
                print(f"Error indexing product {self.id}: {e}")

    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']




class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="product_images")
    image = models.ImageField(upload_to="product")  # Keep this for backward compatibility
    image_url = models.URLField(max_length=500, blank=True, null=True)  # Cloudinary URL
    public_id = models.CharField(max_length=255, blank=True, null=True)  # Cloudinary public_id
    
    def __str__(self):
        return f"Image for {self.product.name}"
    
    def delete(self, *args, **kwargs):
        # Delete from Cloudinary when deleted from database
        from .utils import delete_product_image
        if self.public_id:
            delete_product_image(self.public_id)
        super().delete(*args, **kwargs)
    
    




class Cart(models.Model):
    customer = models.ForeignKey('accounts.Customer', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    vendor = models.ForeignKey('accounts.Vendor', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    color = models.ForeignKey(ColorVariant, on_delete=models.SET_NULL, null=True, blank=True)
    size = models.ForeignKey(SizeVariant, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['customer', 'product', 'color', 'size']

    @property
    def total_price(self):
        base_price = self.product.price * self.quantity
        # Add any additional calculations (e.g., size/color variants)
        return base_price

class Wishlist(models.Model):
    customer = models.ForeignKey('accounts.Customer', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    vendor = models.ForeignKey('accounts.Vendor', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['customer', 'product']
        
        






#checkout and order models
from products.models import Product, ColorVariant, SizeVariant
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
from datetime import timedelta
from django.utils import timezone


class PaymentMethod(models.TextChoices):
    ESEWA = 'esewa', 'eSewa'
    COD = 'cod', 'Cash on Delivery'

class OrderStatus(models.TextChoices):
    PENDING_PAYMENT = 'pending_payment', 'Pending Payment'
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    SHIPPED = 'shipped', 'Shipped'
    DELIVERED = 'delivered', 'Delivered'
    CANCELLED = 'cancelled', 'Cancelled'
    PAYMENT_FAILED = 'payment_failed', 'Payment Failed'

# Add this new model for delivery addresses
class DeliveryAddress(models.Model):
    customer = models.ForeignKey('accounts.Customer', on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField(max_length=100)
    phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$')
    phone_number = models.CharField(validators=[phone_regex], max_length=16)
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Delivery Addresses'

    def __str__(self):
        return f"{self.full_name} - {self.city}"

    def save(self, *args, **kwargs):
        if self.is_default:
            # Set all other addresses of this customer to non-default
            DeliveryAddress.objects.filter(customer=self.customer).update(is_default=False)
        super().save(*args, **kwargs)


class Order(models.Model):
    order_id = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey('accounts.Customer', on_delete=models.CASCADE)
    vendor = models.ForeignKey('accounts.Vendor', on_delete=models.CASCADE)
    delivery_address = models.ForeignKey(DeliveryAddress, on_delete=models.PROTECT)
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        default=PaymentMethod.COD
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING
    )
    payment_status = models.BooleanField(default=False)
    payment_id = models.CharField(max_length=100, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_started = models.BooleanField(default=False)  
    processing_date = models.DateTimeField(null=True, blank=True) 
    shipping_date = models.DateTimeField(null=True, blank=True)
    delivery_date = models.DateTimeField(null=True, blank=True)  
    cancelled_at = models.DateTimeField(null=True, blank=True)  
    cancel_deadline = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    

    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = f"ORD-{timezone.now().strftime('%Y%m%d')}-{str(timezone.now().timestamp())[-4:]}"
            # Set cancel deadline to 24 hours from creation
            self.cancel_deadline = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)
        
        
    def can_cancel(self):
        return (
            self.status in ['pending', 'processing'] 
            and not self.shipping_started 
            and timezone.now() < self.cancel_deadline
        )

    @property
    def time_left_for_cancel(self):
        if not self.can_cancel():
            return 0
        time_left = self.cancel_deadline - timezone.now()
        return max(time_left.total_seconds(), 0)
    
    
    

    def __str__(self):
        return f"Order {self.order_id} - {self.customer}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    color = models.ForeignKey(ColorVariant, on_delete=models.SET_NULL, null=True, blank=True)
    size = models.ForeignKey(SizeVariant, on_delete=models.SET_NULL, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Price at time of order

    def __str__(self):
        return f"{self.order.order_id} - {self.product.name}"

    @property
    def subtotal(self):
        return self.price * self.quantity




class Payment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
    payment_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        default=PaymentMethod.COD
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    payment_response = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.payment_id:
            # Generate payment ID if not provided
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            self.payment_id = f"PAY-{timestamp}-{str(timezone.now().timestamp())[-4:]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.payment_id} - {self.payment_method}"

    class Meta:
        ordering = ['-created_at']




# Add this function to the models.py file
from products.models import Order
def cleanup_abandoned_payments():
    # Find pending payment orders older than 1 hour
    expiry_time = timezone.now() - timedelta(hours=1)
    abandoned_orders = Order.objects.filter(
        status='pending_payment',
        created_at__lt=expiry_time
    )
    
    # Update status to payment_failed
    abandoned_orders.update(status='payment_failed')
    
    return abandoned_orders.count()







# class Review(models.Model):
#     customer = models.ForeignKey('accounts.Customer', on_delete=models.CASCADE)
#     product = models.ForeignKey(Product, on_delete=models.CASCADE)
#     vendor = models.ForeignKey('accounts.Vendor', on_delete=models.CASCADE)
#     rating = models.PositiveIntegerField()
#     review = models.TextField()
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         unique_together = ['customer', 'product']

#     def __str__(self):
#         return f"{self.customer} - {self.product}"
    

from products.models import ProductImage
from django.db.models import Count

# Check how many images have Cloudinary URLs
cloudinary_count = ProductImage.objects.exclude(image_url__isnull=True).count()
total_count = ProductImage.objects.count()

print(f"Images with Cloudinary URLs: {cloudinary_count}/{total_count} ({cloudinary_count/total_count*100:.2f}%)")




from accounts.models import Customer
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
from datetime import timedelta


class Review(models.Model):
    customer   = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="reviews")
    product    = models.ForeignKey("Product",  on_delete=models.CASCADE, related_name="reviews")
    order      = models.ForeignKey("Order",    on_delete=models.CASCADE, related_name="reviews")
    rating     = models.PositiveSmallIntegerField()  # 1–5
    comment    = models.TextField(blank=True)
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    reply = models.TextField(blank=True)  

    class Meta:
        unique_together = [("customer","order","product")]

    def display_name(self):
        if self.is_anonymous:
            return "Anonymous"
        return f"{self.customer.first_name} {self.customer.last_name}"

class ReviewImage(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="images")
    image  = models.ImageField(upload_to="reviews/")
    
    
    
    
    

