from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=150, unique=True, help_text="Category name")
    slug = models.SlugField(max_length=150, unique=True, db_index=True, help_text="URL-friendly identifier")
    description = models.TextField(blank=True, default="", help_text="Category description")
    image = models.URLField(max_length=500, blank=True, default="", help_text="Image URL for category")
    is_active = models.BooleanField(default=True, db_index=True, help_text="Designates whether this category is active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "category"
        verbose_name_plural = "categories"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.name:
            self.name = self.name.strip()
        if not self.slug and self.name:
            self.slug = slugify(self.name)

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            self.slug = slugify(self.name)
        self.full_clean()
        super().save(*args, **kwargs)


class Product(models.Model):
    name = models.CharField(max_length=255, help_text="Product name")
    slug = models.SlugField(max_length=255, unique=True, db_index=True, help_text="Unique URL-friendly slug")
    brand = models.CharField(max_length=150, blank=True, default="", db_index=True, help_text="Product brand or manufacturer")
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        help_text="Product category",
    )
    description = models.TextField(blank=True, default="", help_text="Detailed product description")
    ingredients = models.TextField(blank=True, default="", help_text="Supplement ingredients list")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Base retail price",
    )
    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Discounted sale price",
    )
    stock_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Available inventory units",
    )
    image = models.URLField(max_length=500, blank=True, default="", help_text="Product image URL")
    weight = models.CharField(max_length=50, blank=True, default="", help_text="Weight or size (e.g. '1kg', '60 servings')")
    flavour = models.CharField(max_length=100, blank=True, default="", help_text="Flavour variant (e.g. 'Chocolate', 'Unflavoured')")
    specs = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured specifications (nutritional facts, certifications, etc.)",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether this product is active for sale",
    )
    is_featured = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Featured supplement flag for storefront highlight",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "product"
        verbose_name_plural = "products"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["brand"]),
            models.Index(fields=["price"]),
            models.Index(fields=["is_active", "is_featured"]),
            models.Index(fields=["category", "is_active"]),
        ]

    def __str__(self):
        return self.name

    @property
    def in_stock(self) -> bool:
        return self.stock_quantity > 0

    @property
    def effective_price(self) -> Decimal:
        if self.discount_price is not None and self.discount_price < self.price:
            return self.discount_price
        return self.price

    def clean(self):
        super().clean()
        errors = {}

        if self.price is not None and self.price <= Decimal("0.00"):
            errors["price"] = "Price must be greater than zero."

        if self.discount_price is not None:
            if self.discount_price < Decimal("0.00"):
                errors["discount_price"] = "Discount price cannot be negative."
            elif self.price is not None and self.discount_price >= self.price:
                errors["discount_price"] = "Discount price must be less than the regular price."

        if self.stock_quantity is not None and self.stock_quantity < 0:
            errors["stock_quantity"] = "Stock quantity cannot be negative."

        if errors:
            raise ValidationError(errors)

        if not self.slug and self.name:
            self.slug = slugify(self.name)

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            self.slug = slugify(self.name)
        self.full_clean()
        super().save(*args, **kwargs)
