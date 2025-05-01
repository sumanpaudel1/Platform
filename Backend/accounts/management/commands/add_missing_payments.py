from django.core.management.base import BaseCommand
from accounts.models import Subscription, SubscriptionPayment
from django.utils import timezone
import uuid

class Command(BaseCommand):
    help = 'Creates missing payment records for existing subscriptions'
    
    def handle(self, *args, **options):
        # Get all active subscriptions
        subscriptions = Subscription.objects.filter(status__in=['active', 'trial'])
        count = 0
        
        for subscription in subscriptions:
            # Check if payment already exists
            has_payment = SubscriptionPayment.objects.filter(subscription=subscription).exists()
            
            if not has_payment and subscription.plan:
                # Create a new payment record
                transaction_id = f"MANUAL-{uuid.uuid4()}"
                
                # Determine amount based on plan
                if subscription.plan.name == "Professional":
                    amount = 49.00  # Monthly price for Professional
                elif subscription.plan.name == "Enterprise":
                    amount = 199.00  # Monthly price for Enterprise
                else:
                    amount = 0.00  # Free plan
                
                payment = SubscriptionPayment.objects.create(
                    subscription=subscription,
                    amount=amount,
                    transaction_id=transaction_id,
                    status='completed',
                    payment_method='esewa',
                    payment_date=subscription.start_date,
                    response_data={
                        'note': 'Created by management command',
                        'transaction_id': transaction_id,
                        'amount': str(amount),
                    }
                )
                
                count += 1
                self.stdout.write(self.style.SUCCESS(
                    f"Created payment record for {subscription.vendor.email} - {payment.transaction_id}"
                ))
        
        self.stdout.write(self.style.SUCCESS(f"Added {count} missing payment records"))