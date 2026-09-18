from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
        help_text="Cart owner",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "cart"
        verbose_name_plural = "carts"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Cart ({self.user.email})"

    @property
    def total_items(self) -> int:
        return sum((item.quantity for item in self.items.all()), 0)

    @property
    def subtotal(self) -> Decimal:
        return sum(
            (item.line_total for item in self.items.select_related("product")),
            Decimal("0.00"),
        )

    @property
    def is_empty(self) -> bool:
        return not self.items.exists()


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Associated shopping cart",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="cart_items",
        help_text="Selected product. PROTECT prevents accidental deletion of products in active carts.",
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Quantity of item (must be >= 1)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "cart item"
        verbose_name_plural = "cart items"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="unique_cart_product"),
            models.CheckConstraint(check=models.Q(quantity__gt=0), name="cart_item_quantity_gt_zero"),
        ]

    def __str__(self):
        return f"{self.quantity}x {self.product.name} in {self.cart}"

    @property
    def unit_price(self) -> Decimal:
        return self.product.price

    @property
    def effective_price(self) -> Decimal:
        """
        Safely computes the current effective unit price from the live database product.
        If discount_price is present and valid (0 <= discount_price < price), returns discount_price.
        Otherwise falls back to the standard product price.
        """
        product = self.product
        if (
            product.discount_price is not None
            and Decimal("0.00") <= product.discount_price < product.price
        ):
            return product.discount_price
        return product.price

    @property
    def line_total(self) -> Decimal:
        return self.effective_price * Decimal(self.quantity)

    def clean(self):
        super().clean()
        errors = {}

        if self.quantity is not None and self.quantity <= 0:
            errors["quantity"] = "Quantity must be at least 1."

        if self.product_id and self.pk is None:
            product = self.product
            if not product.is_active:
                errors["product"] = "Cannot add an inactive product to cart."
            if not product.category.is_active:
                errors["product"] = "Cannot add a product from an inactive category to cart."
        if self.product_id and self.quantity is not None:
            product = self.product
            if self.quantity > product.stock_quantity:
                errors["quantity"] = (
                    f"Requested quantity ({self.quantity}) exceeds available stock ({product.stock_quantity})."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
