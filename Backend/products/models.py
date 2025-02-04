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
    color_name = models.CharField(max_length=100)
    image = models.ImageField(upload_to="color_variants", blank=True, null=True)

    class Meta:
        unique_together = ['vendor', 'color_name']

    def __str__(self):
        return f"{self.color_name} - {self.vendor.first_name}"

class SizeVariant(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='sizes')
    size_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ['vendor', 'size_name']

    def __str__(self):
        return f"{self.size_name} - {self.vendor.email}"


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
    color_variant = models.ManyToManyField(ColorVariant, blank=True)
    size_variant = models.ManyToManyField(SizeVariant, blank=True)
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
    
    


