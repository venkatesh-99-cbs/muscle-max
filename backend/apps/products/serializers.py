from decimal import Decimal

from rest_framework import serializers

from apps.products.models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "image",
            "is_active",
            "product_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "product_count")

    def validate_name(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Category name cannot be blank.")
        return cleaned


class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_slug = serializers.CharField(source="category.slug", read_only=True)
    in_stock = serializers.BooleanField(read_only=True)
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "brand",
            "category",
            "category_name",
            "category_slug",
            "price",
            "discount_price",
            "effective_price",
            "image",
            "in_stock",
            "stock_quantity",
            "is_featured",
            "is_active",
            "created_at",
        )
        read_only_fields = fields


class ProductDetailSerializer(serializers.ModelSerializer):
    category_detail = CategorySerializer(source="category", read_only=True)
    in_stock = serializers.BooleanField(read_only=True)
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "brand",
            "category",
            "category_detail",
            "description",
            "ingredients",
            "price",
            "discount_price",
            "effective_price",
            "stock_quantity",
            "in_stock",
            "image",
            "weight",
            "flavour",
            "specs",
            "is_active",
            "is_featured",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "in_stock", "effective_price", "created_at", "updated_at")


class ProductWriteSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(required=False, allow_blank=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "brand",
            "category",
            "description",
            "ingredients",
            "price",
            "discount_price",
            "stock_quantity",
            "image",
            "weight",
            "flavour",
            "specs",
            "is_active",
            "is_featured",
        )
        read_only_fields = ("id",)

    def validate_name(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Product name cannot be blank.")
        return cleaned

    def validate_price(self, value):
        if value is None or value <= Decimal("0.00"):
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    def validate_discount_price(self, value):
        if value is not None and value < Decimal("0.00"):
            raise serializers.ValidationError("Discount price cannot be negative.")
        return value

    def validate_stock_quantity(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Stock quantity cannot be negative.")
        return value

    def validate(self, attrs):
        price = attrs.get("price")
        discount_price = attrs.get("discount_price")

        # In partial updates (PATCH), retrieve price from instance if not sent
        if price is None and self.instance:
            price = self.instance.price

        if discount_price is None and self.instance and "discount_price" not in attrs:
            discount_price = self.instance.discount_price

        if discount_price is not None and price is not None:
            if discount_price >= price:
                raise serializers.ValidationError(
                    {"discount_price": "Discount price must be less than the regular price."}
                )

        return attrs
