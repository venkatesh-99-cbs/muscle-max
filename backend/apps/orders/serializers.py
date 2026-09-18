from rest_framework import serializers

from apps.orders.models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product",
            "product_name",
            "product_brand",
            "quantity",
            "price_at_purchase",
            "line_total",
        )
        read_only_fields = fields


class OrderListSerializer(serializers.ModelSerializer):
    items_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "order_number",
            "status",
            "payment_status",
            "total",
            "items_count",
            "created_at",
        )
        read_only_fields = fields


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    items_count = serializers.IntegerField(read_only=True)
    customer_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "order_number",
            "customer_email",
            "status",
            "payment_status",
            "payment_method",
            "shipping_address",
            "total",
            "items_count",
            "items",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class OrderCreateSerializer(serializers.Serializer):
    shipping_address = serializers.CharField(
        required=True,
        allow_blank=False,
        help_text="Full street and delivery address.",
    )
    payment_method = serializers.CharField(
        required=False,
        default="cash_on_delivery",
        help_text="Payment method (e.g. 'cash_on_delivery', 'card', 'upi').",
    )

    def validate_shipping_address(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Shipping address cannot be empty.")
        return cleaned


class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=Order.STATUS_CHOICES,
        required=True,
        help_text="Target order status.",
    )
