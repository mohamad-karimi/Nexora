from django.db import models

__all__ = ["Payment"]


class Payment(models.Model):
    """
    A payment attempt/transaction against an order. An order can have
    more than one payment row over time (e.g. a failed attempt
    followed by a successful retry), which is why this is a separate
    model rather than fields on Order.
    """

    class Method(models.TextChoices):
        CARD = "card", "Credit/Debit Card"
        CASH_ON_DELIVERY = "cod", "Cash on Delivery"
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"
        WALLET = "wallet", "Wallet"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    order = models.ForeignKey(
        "orders.Order", on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(
        max_length=255, unique=True, null=True, blank=True
    )
    payment_method = models.CharField(
        max_length=20, choices=Method.choices, default=Method.CARD
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_date"]

    def __str__(self):
        return f"Payment #{self.pk} for {self.order.order_number}"
