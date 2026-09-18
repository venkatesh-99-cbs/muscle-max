from decimal import Decimal

from rest_framework import serializers

from apps.cart.models import Cart, CartItem
from apps.products.models import Product


class CartItemProductSummarySerializer(serializers.ModelSerializer):
    in_stock = serializers.BooleanField(read_only=True)
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "brand",
            "image",
            "price",
            "discount_price",
            "effective_price",
            "stock_quantity",
            "in_stock",
        )
        read_only_fields = fields


class CartItemSerializer(serializers.ModelSerializer):
    product_details = CartItemProductSummarySerializer(source="product", read_only=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = (
            "id",
            "product",
            "product_details",
            "quantity",
            "unit_price",
            "effective_price",
            "line_total",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "product",
            "product_details",
            "unit_price",
            "effective_price",
            "line_total",
            "created_at",
            "updated_at",
        )


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = (
            "id",
            "items",
            "total_items",
            "subtotal",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CartItemAddSerializer(serializers.Serializer):
    product = serializers.CharField(
        required=True,
        help_text="Product numeric ID or slug string.",
    )
    quantity = serializers.IntegerField(
        required=False,
        default=1,
        min_value=1,
        help_text="Quantity to add (must be >= 1).",
    )


class CartItemUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(
        required=True,
        min_value=1,
        help_text="Updated quantity (must be >= 1).",
    )
