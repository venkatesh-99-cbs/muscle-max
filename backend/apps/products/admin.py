from django.contrib import admin

from apps.products.models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "brand",
        "category",
        "price",
        "discount_price",
        "stock_quantity",
        "in_stock_display",
        "is_active",
        "is_featured",
    )
    list_filter = ("is_active", "is_featured", "category", "brand")
    search_fields = ("name", "brand", "slug", "description", "ingredients")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "slug", "brand", "category", "image"),
            },
        ),
        (
            "Pricing & Inventory",
            {
                "fields": ("price", "discount_price", "stock_quantity"),
            },
        ),
        (
            "Supplement Attributes",
            {
                "fields": ("weight", "flavour", "specs"),
            },
        ),
        (
            "Details & Ingredients",
            {
                "fields": ("description", "ingredients"),
            },
        ),
        (
            "Status & Visibility",
            {
                "fields": ("is_active", "is_featured"),
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

    @admin.display(boolean=True, description="In Stock")
    def in_stock_display(self, obj):
        return obj.in_stock
