"""
Payment Service — Celery Beat Tasks
======================================
Automated payout dispatch tasks.  Scheduled in settings.CELERY_BEAT_SCHEDULE.

The admin sets payout_period on each vendor's VendorPaymentTerms.
These tasks run on the matching schedule and dispatch all due payouts
to the Payment System via the RabbitMQ event bus.
"""

import logging
from celery import shared_task
from .services import dispatch_due_payouts

logger = logging.getLogger(__name__)


@shared_task(name='payment_service.dispatch_daily_payouts', bind=True, max_retries=3)
def dispatch_daily_payouts(self):
    """Runs every day at 23:55. Dispatches all pending 'daily' vendor payouts."""
    try:
        result = dispatch_due_payouts('daily')
        logger.info("[ecommerce] Daily payout dispatch: %s", result)
        return result
    except Exception as exc:
        logger.error("[ecommerce] Daily payout task failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='payment_service.dispatch_weekly_payouts', bind=True, max_retries=3)
def dispatch_weekly_payouts(self):
    """Runs every Monday at 23:55. Dispatches all pending 'weekly' vendor payouts."""
    try:
        result = dispatch_due_payouts('weekly')
        logger.info("[ecommerce] Weekly payout dispatch: %s", result)
        return result
    except Exception as exc:
        logger.error("[ecommerce] Weekly payout task failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='payment_service.dispatch_monthly_payouts', bind=True, max_retries=3)
def dispatch_monthly_payouts(self):
    """Runs on the 1st of each month at 23:55. Dispatches 'monthly' vendor payouts."""
    try:
        result = dispatch_due_payouts('monthly')
        logger.info("[ecommerce] Monthly payout dispatch: %s", result)
        return result
    except Exception as exc:
        logger.error("[ecommerce] Monthly payout task failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)
