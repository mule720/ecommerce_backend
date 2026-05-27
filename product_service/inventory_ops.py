"""Inventory reservation/release helpers for cross-system workflows."""
from django.db import transaction

from .models import Product, InventorySyncLog


def reserve_inventory_lines(*, lines, source_reference: str, context_message: str = "Inventory reserved"):
    """
    Reserve inventory for a list of lines.

    Each line expects:
    - sku (required)
    - quantity (required, int > 0)
    - vendor_id (optional)
    """
    reserved = []
    with transaction.atomic():
        # First pass: validate all stock before mutating
        products = []
        for line in lines:
            sku = line.get("sku")
            qty = int(line.get("quantity", 0))
            vendor_id = line.get("vendor_id")
            if not sku or qty <= 0:
                raise ValueError("Invalid inventory reservation line")

            queryset = Product.objects.select_for_update().filter(sku=sku)
            if vendor_id:
                queryset = queryset.filter(vendor_id=vendor_id)
            product = queryset.first()
            if not product:
                raise ValueError(f"Product not found for SKU={sku}")
            if product.quantity < qty:
                raise ValueError(f"Insufficient stock for SKU={sku}")
            products.append((product, qty))

        # Second pass: apply reservation
        for product, qty in products:
            product.quantity -= qty
            product.save(update_fields=["quantity", "updated_at"])
            log = InventorySyncLog.objects.create(
                product=product,
                direction="ecom_to_erp",
                quantity_delta=qty,
                source_reference=source_reference,
                status="pending",
                message=context_message,
                payload={"operation": "reserve"},
            )
            reserved.append({"sku": product.sku, "quantity": qty, "log_id": log.id})
    return reserved


def release_inventory_lines(*, lines, source_reference: str, context_message: str = "Inventory released"):
    """Release previously reserved inventory for a list of lines."""
    released = []
    with transaction.atomic():
        for line in lines:
            sku = line.get("sku")
            qty = int(line.get("quantity", 0))
            vendor_id = line.get("vendor_id")
            if not sku or qty <= 0:
                raise ValueError("Invalid inventory release line")

            queryset = Product.objects.select_for_update().filter(sku=sku)
            if vendor_id:
                queryset = queryset.filter(vendor_id=vendor_id)
            product = queryset.first()
            if not product:
                raise ValueError(f"Product not found for SKU={sku}")

            product.quantity += qty
            product.save(update_fields=["quantity", "updated_at"])
            log = InventorySyncLog.objects.create(
                product=product,
                direction="ecom_to_erp",
                quantity_delta=-qty,
                source_reference=source_reference,
                status="pending",
                message=context_message,
                payload={"operation": "release"},
            )
            released.append({"sku": product.sku, "quantity": qty, "log_id": log.id})
    return released
