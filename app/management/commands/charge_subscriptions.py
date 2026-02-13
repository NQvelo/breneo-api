from django.core.management.base import BaseCommand
from django.utils import timezone
from app.models import UserSubscription
from app.views import perform_automatic_charge
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Processes due subscriptions and performs automatic charges via BOG'

    def handle(self, *args, **options):
        today = timezone.now().date()
        due_subscriptions = UserSubscription.objects.filter(
            is_active=True,
            next_payment_date__lte=today
        )

        self.stdout.write(f"Found {due_subscriptions.count()} due subscriptions.")

        for sub in due_subscriptions:
            self.stdout.write(f"Processing subscription for user: {sub.user.email}")
            
            success, result = perform_automatic_charge(sub)
            
            if success:
                self.stdout.write(self.style.SUCCESS(
                    f"Successfully initiated charge for {sub.user.email}. Order ID: {result.get('id')}"
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f"Failed to charge {sub.user.email}: {result}"
                ))
                # Optionally: notify user or admin about failure
                # sub.is_active = False
                # sub.save()

        self.stdout.write(self.style.SUCCESS("Finished processing subscriptions."))
