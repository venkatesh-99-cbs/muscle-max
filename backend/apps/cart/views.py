from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart.serializers import (
    CartItemAddSerializer,
    CartItemSerializer,
    CartItemUpdateSerializer,
    CartSerializer,
)
from apps.cart.services import (
    add_to_cart,
    clear_cart,
    get_or_create_user_cart,
    remove_cart_item,
    update_cart_item_quantity,
)


def handle_service_validation(func):
    """
    Decorator to convert Django ValidationError from domain service layer
    into DRF ValidationError with proper HTTP 400 response structure.
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DjangoValidationError as e:
            if hasattr(e, "message_dict"):
                raise DRFValidationError(e.message_dict)
            raise DRFValidationError(e.messages)

    return wrapper


class CartView(APIView):
    """
    Retrieve the authenticated user's current shopping cart.
    GET /api/cart/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart = get_or_create_user_cart(request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CartItemView(APIView):
    """
    Add a product to the user's shopping cart.
    POST /api/cart/items/
    """

    permission_classes = [IsAuthenticated]

    @handle_service_validation
    def post(self, request):
        serializer = CartItemAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart = get_or_create_user_cart(request.user)
        product_ref = serializer.validated_data["product"]
        quantity = serializer.validated_data.get("quantity", 1)

        cart_item = add_to_cart(cart, product_ref, quantity)
        response_serializer = CartItemSerializer(cart_item)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class CartItemDetailView(APIView):
    """
    Update quantity or remove an item from the user's shopping cart.
    PATCH /api/cart/items/<id>/
    DELETE /api/cart/items/<id>/
    """

    permission_classes = [IsAuthenticated]

    @handle_service_validation
    def patch(self, request, pk):
        serializer = CartItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart = get_or_create_user_cart(request.user)
        quantity = serializer.validated_data["quantity"]

        cart_item = update_cart_item_quantity(cart, pk, quantity)
        response_serializer = CartItemSerializer(cart_item)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        cart = get_or_create_user_cart(request.user)
        removed = remove_cart_item(cart, pk)
        if not removed:
            raise NotFound({"detail": "Item not found in your cart."})
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClearCartView(APIView):
    """
    Clear all items in the authenticated user's shopping cart.
    POST /api/cart/clear/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        cart = get_or_create_user_cart(request.user)
        deleted_count = clear_cart(cart)
        return Response(
            {
                "detail": "Cart cleared successfully.",
                "deleted_items_count": deleted_count,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request):
        cart = get_or_create_user_cart(request.user)
        clear_cart(cart)
        return Response(status=status.HTTP_204_NO_CONTENT)
