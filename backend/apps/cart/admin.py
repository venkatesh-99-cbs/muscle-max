from django.contrib import admin

from apps.cart.models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ("product", "quantity", "unit_price", "effective_price", "line_total", "created_at")
    can_delete = True


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "total_items", "subtotal", "created_at", "updated_at")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    readonly_fields = ("created_at", "updated_at", "total_items", "subtotal")
    inlines = [CartItemInline]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cart",
        "product",
        "quantity",
        "unit_price",
        "effective_price",
        "line_total",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("cart__user__email", "product__name", "product__slug")
    readonly_fields = ("unit_price", "effective_price", "line_total", "created_at", "updated_at")
