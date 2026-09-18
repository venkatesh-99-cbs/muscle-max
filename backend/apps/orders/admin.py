from django.contrib import admin

from apps.orders.models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "product",
        "product_name",
        "product_brand",
        "quantity",
        "price_at_purchase",
        "line_total",
    )
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "user",
        "status",
        "payment_status",
        "total",
        "items_count",
        "created_at",
    )
    list_filter = ("status", "payment_status", "created_at")
    search_fields = ("order_number", "user__email", "user__first_name", "shipping_address")
    readonly_fields = ("order_number", "total", "items_count", "created_at", "updated_at")
    inlines = [OrderItemInline]

    fieldsets = (
        (
            "Order Details",
            {
                "fields": ("order_number", "user", "total", "items_count"),
            },
        ),
        (
            "Fulfillment & Payment",
            {
                "fields": ("status", "payment_status", "payment_method"),
            },
        ),
        (
            "Shipping",
            {
                "fields": ("shipping_address",),
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "product_name",
        "product_brand",
        "quantity",
        "price_at_purchase",
        "line_total",
    )
    search_fields = ("order__order_number", "product_name", "product_brand")
    readonly_fields = (
        "order",
        "product",
        "product_name",
        "product_brand",
        "quantity",
        "price_at_purchase",
        "line_total",
    )
