import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Order(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_SHIPPED = "shipped"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_SHIPPED, "Shipped"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    VALID_TRANSITIONS = {
        STATUS_PENDING: [STATUS_PAID, STATUS_CANCELLED],
        STATUS_PENDING: [STATUS_PAID, STATUS_SHIPPED, STATUS_CANCELLED],
        STATUS_PAID: [STATUS_SHIPPED, STATUS_CANCELLED],
        STATUS_SHIPPED: [STATUS_DELIVERED, STATUS_CANCELLED],
        STATUS_SHIPPED: [STATUS_DELIVERED],  # In-transit orders cannot be cancelled directly
        STATUS_DELIVERED: [],  # Terminal
        STATUS_CANCELLED: [],  # Terminal
    }

    PAYMENT_PENDING = "pending"
    PAYMENT_PAID = "paid"
    PAYMENT_FAILED = "failed"

    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_PENDING, "Pending"),
        (PAYMENT_PAID, "Paid"),
        (PAYMENT_FAILED, "Failed"),
    )

    order_number = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Unique customer order reference",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
        help_text="Customer who placed the order",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        help_text="Current fulfillment lifecycle status",
    )
    payment_method = models.CharField(
        max_length=50,
        default="cash_on_delivery",
        help_text="Selected payment method",
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_PENDING,
        db_index=True,
        help_text="Payment transaction state",
    )
    shipping_address = models.TextField(
        help_text="Destination shipping address provided at checkout",
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Final order total calculated server-side",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "order"
        verbose_name_plural = "orders"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order_number"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"Order #{self.order_number} ({self.user.email})"

    @property
    def items_count(self) -> int:
        return sum((item.quantity for item in self.items.all()), 0)

    @property
    def can_cancel(self) -> bool:
        return self.status in [self.STATUS_PENDING, self.STATUS_PAID]

    def clean(self):
        super().clean()
        if not self.shipping_address or not self.shipping_address.strip():
            raise ValidationError({"shipping_address": "Shipping address cannot be empty."})

        # Validate status transitions for existing orders
        if self.pk:
            original = Order.objects.filter(pk=self.pk).values("status").first()
            if original and original["status"] != self.status:
                current_status = original["status"]
                allowed = self.VALID_TRANSITIONS.get(current_status, [])
                if self.status not in allowed:
                    raise ValidationError(
                        {
                            "status": (
                                f"Cannot transition order status from '{current_status}' to '{self.status}'. "
                                f"Allowed transitions: {allowed or 'None (terminal state)'}."
                            )
                        }
                    )

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = f"ORD-{uuid.uuid4().hex[:10].upper()}"
        self.full_clean()
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Parent order",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="order_items",
        help_text="Purchased product",
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Quantity purchased (must be >= 1)",
    )
    price_at_purchase = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Unit price snapshot at the time of purchase",
    )
    product_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Snapshot of product name at purchase",
    )
    product_brand = models.CharField(
        max_length=150,
        blank=True,
        default="",
        help_text="Snapshot of product brand at purchase",
    )

    class Meta:
        verbose_name = "order item"
        verbose_name_plural = "order items"
        ordering = ["id"]

    def __str__(self):
        name = self.product_name or (self.product.name if self.product_id else "Product")
        return f"{self.quantity}x {name} @ {self.price_at_purchase}"

    @property
    def line_total(self) -> Decimal:
        return self.price_at_purchase * Decimal(self.quantity)

    def clean(self):
        super().clean()
        errors = {}
        if self.quantity is not None and self.quantity <= 0:
            errors["quantity"] = "Quantity must be at least 1."
        if self.price_at_purchase is not None and self.price_at_purchase <= Decimal("0.00"):
            errors["price_at_purchase"] = "Price at purchase must be greater than zero."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.product_id:
            if not self.product_name:
                self.product_name = self.product.name
            if not self.product_brand:
                self.product_brand = self.product.brand
        self.full_clean()
        super().save(*args, **kwargs)
