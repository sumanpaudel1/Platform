import hmac
import hashlib
import base64

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
        transaction_uuid = f"{order.order_id}"  # Simplified UUID
        
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
        
        return self.test_url, params