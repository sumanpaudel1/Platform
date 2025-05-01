import hmac
import hashlib
import base64
import uuid
import time

class EsewaPayment:
    def __init__(self):
        self.merchant_id = "EPAYTEST"
        self.test_url = "https://rc-epay.esewa.com.np/api/epay/main/v2/form"
        self.success_url = "http://127.0.0.1:8080/esewa/success/"
        self.failure_url = "http://127.0.0.1:8080/esewa/failure/"
        self.secret_key = "8gBm/:&EnhH.1/q"

    def generate_signature(self, total_amount, transaction_uuid, product_code):
        # Create signature string in exact format required
        message = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
        
        # Generate HMAC signature
        hmac_obj = hmac.new(
            key=self.secret_key.encode(),
            msg=message.encode(),
            digestmod=hashlib.sha256
        )
        signature = base64.b64encode(hmac_obj.digest()).decode()
        return signature

    def generate_payment_data(self, order):
        # Format amount to 2 decimal places
        amount = "{:.2f}".format(float(order.total_amount))
        
        # Generate a unique transaction UUID that includes the order ID
        # but is guaranteed to be unique for each payment attempt
        unique_id = f"{order.order_id}-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        transaction_uuid = unique_id
        
        params = {
            'amount': amount,
            'tax_amount': "0",
            'total_amount': amount,  # Same as amount if no tax
            'transaction_uuid': transaction_uuid,
            'product_code': self.merchant_id,
            'product_service_charge': "0",
            'product_delivery_charge': "0",
            'success_url': self.success_url,
            'failure_url': self.failure_url,
            'signed_field_names': "total_amount,transaction_uuid,product_code",
        }
        
        # Generate signature
        params['signature'] = self.generate_signature(
            total_amount=amount,
            transaction_uuid=transaction_uuid,
            product_code=self.merchant_id
        )
        
        # Store original order ID in session or somewhere to retrieve after payment
        return self.test_url, params
    




import cloudinary
import cloudinary.uploader
from django.conf import settings

# Configure Cloudinary using your existing CLOUDINARY_STORAGE dictionary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
    api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
    api_secret=settings.CLOUDINARY_STORAGE['API_SECRET'],
    secure=True
)

def upload_product_image(image_file, vendor_id, product_id=None):
    try:
        # Create a folder structure based on CLOUDINARY_STORAGE prefix
        prefix = settings.CLOUDINARY_STORAGE.get('PREFIX', 'platform/products')
        folder = f"{prefix}/{vendor_id}"
        if product_id:
            folder = f"{folder}/{product_id}"
            
        # Upload to Cloudinary with automatic format and quality
        result = cloudinary.uploader.upload(
            image_file,
            folder=folder,
            resource_type="image",
            use_filename=True,
            unique_filename=True,
            transformation=[
                {"quality": "auto:good", "fetch_format": "auto"}
            ]
        )
        
        return {
            'url': result['secure_url'],
            'public_id': result['public_id']
        }
    except Exception as e:
        print(f"Cloudinary upload error: {str(e)}")
        return None

def delete_product_image(public_id):
    """
    Delete a product image from Cloudinary
    
    Args:
        public_id: Public ID of the image to delete
        
    Returns:
        bool: True if deleted successfully, False otherwise
    """
    try:
        result = cloudinary.uploader.destroy(public_id)
        return result.get('result') == 'ok'
    except Exception as e:
        print(f"Cloudinary delete error: {str(e)}")
        return False