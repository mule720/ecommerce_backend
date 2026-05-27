"""
Returns Service Models - Return request management
Note: ReturnRequest model is defined in order_service to avoid duplication
This service extends returns functionality with shipment and history tracking
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from order_service.models import ReturnRequest


class ReturnShipment(models.Model):
    """Track return shipments"""
    
    return_request = models.OneToOneField(
        ReturnRequest,
        on_delete=models.CASCADE,
        related_name='shipment'
    )
    
    tracking_number = models.CharField(max_length=100, unique=True)
    carrier = models.CharField(max_length=100)
    
    sent_at = models.DateTimeField(auto_now_add=True)
    received_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'returns_service_return_shipments'
    
    def __str__(self):
        return f"Return Shipment {self.tracking_number}"


class ReturnHistory(models.Model):
    """Track status changes for return requests"""
    
    return_request = models.ForeignKey(
        ReturnRequest,
        on_delete=models.CASCADE,
        related_name='history'
    )
    
    status_from = models.CharField(max_length=20)
    status_to = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    reason = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'returns_service_return_history'
        ordering = ['-changed_at']
    
    def __str__(self):
        return f"{self.return_request.id}: {self.status_from} → {self.status_to}"
