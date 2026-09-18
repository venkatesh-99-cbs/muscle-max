from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.orders.models import Order
from apps.orders.serializers import (
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
    OrderStatusUpdateSerializer,
)
from apps.orders.services import (
    cancel_order,
    create_order_from_cart,
    update_order_status,
)


class OrderViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Order management.
    - POST /api/orders/ : Create order from authenticated user's cart.
    - GET /api/orders/ : List user's orders (admin sees all).
    - GET /api/orders/<id>/ : Retrieve order details.
    - PATCH /api/orders/<id>/ : Update order status (admin) or cancel (customer).
    - POST /api/orders/<id>/cancel/ : Cancel order and restore inventory.
    """

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]
    lookup_value_regex = r"[^/.]+"

    def _is_admin(self) -> bool:
        user = self.request.user
        return bool(user and user.is_authenticated and getattr(user, "is_admin_role", False))

    def get_queryset(self):
        if self._is_admin():
            return (
                Order.objects.prefetch_related("items", "items__product")
                .select_related("user")
                .all()
            )
        return (
            Order.objects.prefetch_related("items", "items__product")
            .filter(user=self.request.user)
        )

    def get_serializer_class(self):
        if self.action == "list":
            return OrderListSerializer
        elif self.action == "create":
            return OrderCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return OrderStatusUpdateSerializer
        return OrderDetailSerializer

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_value = self.kwargs.get("pk")
        lookup_str = str(lookup_value).strip()

        if lookup_str.isdigit():
            obj = get_object_or_404(queryset, id=int(lookup_str))
        else:
            obj = get_object_or_404(queryset, order_number=lookup_str)

        self.check_object_permissions(self.request, obj)
        return obj

    def create(self, request, *args, **kwargs):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        shipping_address = serializer.validated_data["shipping_address"]
        payment_method = serializer.validated_data.get("payment_method", "cash_on_delivery")

        try:
            order = create_order_from_cart(
                user=request.user,
                shipping_address=shipping_address,
                payment_method=payment_method,
            )
        except DjangoValidationError as e:
            if hasattr(e, "message_dict"):
                raise DRFValidationError(e.message_dict)
            raise DRFValidationError(e.messages)

        response_serializer = OrderDetailSerializer(order)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        order = self.get_object()
        if not self._is_admin():
            raise PermissionDenied("Only administrators can update order status via PATCH. Customers must use the cancel endpoint.")

        serializer = OrderStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data["status"]
        is_admin = self._is_admin()
        try:
            order = update_order_status(order, new_status, is_admin=True)
        except DjangoValidationError as e:
            raise DRFValidationError(e.message_dict if hasattr(e, "message_dict") else e.messages)

        if not is_admin:
            if new_status != Order.STATUS_CANCELLED:
                raise PermissionDenied("Customers can only cancel eligible orders.")
            try:
                order = cancel_order(order, request.user, is_admin=False)
            except DjangoValidationError as e:
                raise DRFValidationError(e.message_dict if hasattr(e, "message_dict") else e.messages)
        else:
            try:
                order = update_order_status(order, new_status, is_admin=True)
            except DjangoValidationError as e:
                raise DRFValidationError(e.message_dict if hasattr(e, "message_dict") else e.messages)

        return Response(OrderDetailSerializer(order).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        order = self.get_object()
        try:
            order = cancel_order(order, request.user, is_admin=self._is_admin())
        except DjangoValidationError as e:
            raise DRFValidationError(e.message_dict if hasattr(e, "message_dict") else e.messages)

        return Response(
            {
                "detail": "Order cancelled successfully.",
                "order": OrderDetailSerializer(order).data,
            },
            status=status.HTTP_200_OK,
        )
