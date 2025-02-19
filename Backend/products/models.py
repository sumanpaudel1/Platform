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
        super(Product, self).save(*args, **kwargs)

    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="product_images")
    image = models.ImageField(upload_to="product")

    def __str__(self):
        return f"Image for {self.product.name}"
    
    




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
        
        

class Order(models.Model):
    customer = models.ForeignKey('accounts.Customer', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    vendor = models.ForeignKey('accounts.Vendor', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    color = models.ForeignKey(ColorVariant, on_delete=models.SET_NULL, null=True, blank=True)
    size = models.ForeignKey(SizeVariant, on_delete=models.SET_NULL, null=True, blank=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['customer', 'product', 'color', 'size']

    def __str__(self):
        return f"{self.customer} - {self.product}"
    
    @property
    def total_price(self):
        return self.quantity * self.product.price
    

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
    
    