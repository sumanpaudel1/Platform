import random
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def generate_otp():
    try:
        return random.randint(100000, 999999)
    except Exception as e:
        logger.error(f"Error generating OTP: {str(e)}")
        raise

def send_otp_to_email(email, otp):
    try:
        subject = "Your OTP Code"
        message = f"Your OTP is {otp}. It expires in 1.5 minutes."
        email_from = settings.EMAIL_HOST_USER
        recipient_list = [email]
        
        sent = send_mail(
            subject,
            message,
            email_from,
            recipient_list,
            fail_silently=False
        )
        
        if sent:
            logger.info(f"OTP sent successfully to {email}")
            return True
        logger.error(f"Failed to send OTP to {email}")
        return False
        
    except Exception as e:
        logger.error(f"Error sending OTP email: {str(e)}")
        raise