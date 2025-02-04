from django.test import TestCase
from .models import Product
from accounts.models import Vendor

class ProductModelTest(TestCase):
    def setUp(self):
        self.vendor = Vendor.objects.create(
            email='vendor@example.com',
            phone_number='1234567890',
            first_name='John',
            last_name='Doe',
            middle_name='A',
            password='password123'
        )
        self.product = Product.objects.create(
            name='T-Shirt',
            description='A comfortable cotton t-shirt',
            size='M',
            color='Blue',
            price=19.99,
            vendor=self.vendor
        )

    def test_product_creation(self):
        self.assertEqual(self.product.name, 'T-Shirt')
        self.assertEqual(self.product.description, 'A comfortable cotton t-shirt')
        self.assertEqual(self.product.size, 'M')
        self.assertEqual(self.product.color, 'Blue')
        self.assertEqual(self.product.price, 19.99)
        self.assertEqual(self.product.vendor, self.vendor)

    def test_vendor_access_to_product(self):
        self.assertEqual(self.product.vendor.email, 'vendor@example.com')