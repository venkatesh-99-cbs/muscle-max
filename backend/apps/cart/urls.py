from django.urls import path

from apps.cart.views import CartItemDetailView, CartItemView, CartView, ClearCartView

urlpatterns = [
    path("", CartView.as_view(), name="cart-detail"),
    path("items/", CartItemView.as_view(), name="cart-items"),
    path("items/<int:pk>/", CartItemDetailView.as_view(), name="cart-item-detail"),
    path("clear/", ClearCartView.as_view(), name="cart-clear"),
]
