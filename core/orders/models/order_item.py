from django.db import models

__all__ = ["OrderItem"]


class OrderItem(models.Model):
    """
    A single line item of an order. Product name and unit price are
    snapshotted at purchase time (`product_name`, `unit_price`) so the
    order/invoice stays accurate even if the product is later
    renamed, repriced, or removed altogether - hence `product` and
    `vendor` use SET_NULL rather than CASCADE/PROTECT.
    """

    order = models.ForeignKey(
        "orders.Order", on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        "shop.Product",
        on_delete=models.SET_NULL,
        null=True,
        related_name="order_items",
    )
    vendor = models.ForeignKey(
        "vendors.Vendor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    product_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Snapshot of the product name at the time of purchase.",
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Snapshot of the product's price at the time of purchase.",
    )
    created_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"

    @property
    def total_price(self):
        return self.unit_price * self.quantity

    def save(self, *args, **kwargs):
        if not self.product_name and self.product_id:
            self.product_name = self.product.name
        if not self.vendor_id and self.product_id and self.product.vendor_id:
            self.vendor_id = self.product.vendor_id
        super().save(*args, **kwargs)
