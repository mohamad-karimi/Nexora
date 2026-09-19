import uuid

from django.conf import settings
from django.db import models

__all__ = ["Order", "generate_order_number"]


def generate_order_number():
    """Short, unguessable, human-shareable order reference
    (e.g. on an invoice).
    """
    return uuid.uuid4().hex[:12].upper()


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    order_number = models.CharField(
        max_length=20,
        unique=True,
        default=generate_order_number,
        editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="orders",
        help_text=(
            "Kept nullable so order/financial history survives "
            "account deletion."
        ),
    )
    shipping_address = models.ForeignKey(
        "orders.Address",
        on_delete=models.PROTECT,
        related_name="shipping_orders",
    )
    billing_address = models.ForeignKey(
        "orders.Address",
        on_delete=models.PROTECT,
        related_name="billing_orders",
        null=True,
        blank=True,
        help_text="Defaults to the shipping address when left empty.",
    )
    coupon = models.ForeignKey(
        "orders.Coupon",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    shipping_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    tracking_code = models.CharField(max_length=100, blank=True)

    created_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_date"]

    def __str__(self):
        return self.order_number

    @property
    def subtotal(self):
        """Sum of order-item totals - always derivable, so it is not stored."""
        return sum((item.total_price for item in self.items.all()), start=0)
