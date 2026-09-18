from django.conf import settings
from django.db import models


class Cart(models.Model):
    """
    A shopping cart. Supports both logged-in users (`user`) and
    anonymous/guest visitors (`session_key`), which is standard for a
    storefront - people should be able to add items before creating
    an account. Exactly one of the two must be set.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
        null=True,
        blank=True,
    )
    session_key = models.CharField(
        max_length=40, null=True, blank=True, unique=True
    )
    created_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(user__isnull=False)
                | models.Q(session_key__isnull=False),
                name="cart_requires_user_or_session",
            )
        ]

    def __str__(self):
        if self.user_id:
            return f"Cart of {self.user}"
        return f"Guest cart ({self.session_key})"

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        return sum((item.subtotal for item in self.items.all()), start=0)


class CartItem(models.Model):
    """
    A line in a cart. Price is intentionally NOT stored here - it is
    read live from the product (via `unit_price`/`subtotal`) so the
    cart always reflects the current price until checkout, at which
    point `orders.OrderItem` takes its own price snapshot.
    """

    cart = models.ForeignKey(
        Cart, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        "shop.Product", on_delete=models.CASCADE, related_name="cart_items"
    )
    quantity = models.PositiveIntegerField(default=1)
    created_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"], name="unique_cart_product"
            )
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def unit_price(self):
        return self.product.final_price

    @property
    def subtotal(self):
        return self.unit_price * self.quantity
