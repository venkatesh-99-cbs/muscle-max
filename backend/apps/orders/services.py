from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.cart.services import get_or_create_user_cart
from apps.orders.models import Order, OrderItem
from apps.products.models import Product


def create_order_from_cart(user, shipping_address: str, payment_method: str = "cash_on_delivery") -> Order:
    """
    Atomically creates an Order from the authenticated user's active shopping cart.
    Locks product inventory using select_for_update to prevent overselling under concurrent checkouts.
    Calculates prices server-side, deducts stock, records historical snapshot data, and clears the cart.
    """
    if not shipping_address or not shipping_address.strip():
        raise ValidationError({"shipping_address": "Shipping address is required."})

    with transaction.atomic():
        cart = get_or_create_user_cart(user)
        cart_items = list(cart.items.select_related("product", "product__category").all())

        if not cart_items:
            raise ValidationError({"cart": "Cannot checkout with an empty cart."})

        product_ids = [item.product_id for item in cart_items]

        # Acquire pessimistic row-level locks on all products to prevent race-condition overselling
        locked_products = {
            p.id: p
            for p in Product.objects.select_for_update()
            .select_related("category")
            .filter(id__in=product_ids)
        }

        order_total = Decimal("0.00")
        items_to_create = []

        # Validate each item under the acquired lock
        for item in cart_items:
            product = locked_products.get(item.product_id)
            if not product:
                raise ValidationError({"product": f"Product '{item.product_id}' does not exist."})

            if not product.is_active:
                raise ValidationError(
                    {"product": f"Product '{product.name}' is no longer active and cannot be ordered."}
                )
            if not product.category.is_active:
                raise ValidationError(
                    {"product": f"Product '{product.name}' belongs to an inactive category."}
                )

            if item.quantity > product.stock_quantity:
                raise ValidationError(
                    {
                        "stock": (
                            f"Insufficient stock for '{product.name}'. "
                            f"Requested: {item.quantity}, Available: {product.stock_quantity}."
                        )
                    }
                )

            unit_price = product.effective_price
            line_total = unit_price * Decimal(item.quantity)
            order_total += line_total

            items_to_create.append(
                {
                    "product": product,
                    "quantity": item.quantity,
                    "price_at_purchase": unit_price,
                    "product_name": product.name,
                    "product_brand": product.brand,
                }
            )

        # Create the Order
        order = Order(
            user=user,
            shipping_address=shipping_address.strip(),
            payment_method=payment_method or "cash_on_delivery",
            status=Order.STATUS_PENDING,
            payment_status=Order.PAYMENT_PENDING,
            total=order_total,
        )
        order.save()

        # Create OrderItems and decrement inventory
        for data in items_to_create:
            product = data["product"]
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=data["quantity"],
                price_at_purchase=data["price_at_purchase"],
                product_name=data["product_name"],
                product_brand=data["product_brand"],
            )

            # Deduct stock
            product.stock_quantity -= data["quantity"]
            product.save(update_fields=["stock_quantity", "updated_at"])

        # Clear the user's cart on successful checkout
        cart.items.all().delete()
        cart.save(update_fields=["updated_at"])

        return order


def cancel_order(order: Order, user, is_admin: bool = False) -> Order:
    """
    Cancels an order and safely restores stock to the product catalog.
    Only orders in 'pending' or 'paid' status may be cancelled.
    Thread-safe and idempotent: row-level locking ensures stock is restored exactly once.
    """
    if not is_admin and order.user != user:
        raise ValidationError({"order": "You do not have permission to cancel this order."})

    with transaction.atomic():
        # Lock the order row to serialize concurrent cancellations
        locked_order = Order.objects.select_for_update().get(pk=order.pk)

        if locked_order.status == Order.STATUS_CANCELLED:
            raise ValidationError({"status": "Order is already cancelled."})

        if not locked_order.can_cancel:
            raise ValidationError(
                {"status": f"Cannot cancel order in '{locked_order.status}' status. Only pending or paid orders may be cancelled."}
            )

        order_items = list(locked_order.items.select_related("product").all())
        product_ids = [item.product_id for item in order_items]

        # Lock products to restore inventory safely
        locked_products = {
            p.id: p
            for p in Product.objects.select_for_update().filter(id__in=product_ids)
        }

        for item in order_items:
            product = locked_products.get(item.product_id)
            if product:
                product.stock_quantity += item.quantity
                product.save(update_fields=["stock_quantity", "updated_at"])

        locked_order.status = Order.STATUS_CANCELLED
        locked_order.save(update_fields=["status", "updated_at"])

        # Sync caller instance
        order.status = Order.STATUS_CANCELLED
        order.updated_at = locked_order.updated_at

        return locked_order


def update_order_status(order: Order, new_status: str, is_admin: bool = False) -> Order:
    """
    Admin workflow to transition an order's fulfillment lifecycle.
    Enforces valid transition state machine and handles inventory restoration on cancellation.
    """
    if not is_admin:
        raise ValidationError({"permission": "Only administrators can update order status directly."})

    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)

        if new_status == locked_order.status:
            return locked_order

        if new_status == Order.STATUS_CANCELLED:
            return cancel_order(locked_order, locked_order.user, is_admin=True)

        allowed = Order.VALID_TRANSITIONS.get(locked_order.status, [])
        if new_status not in allowed:
            raise ValidationError(
                {
                    "status": (
                        f"Cannot transition order from '{locked_order.status}' to '{new_status}'. "
                        f"Allowed transitions: {allowed or 'None (terminal state)'}."
                    )
                }
            )

        # Business logic validation: Prepaid orders cannot be shipped before payment is confirmed
        if (
            new_status == Order.STATUS_SHIPPED
            and locked_order.payment_method != "cash_on_delivery"
            and locked_order.payment_status != Order.PAYMENT_PAID
        ):
            raise ValidationError(
                {"payment_status": "Prepaid orders cannot be shipped until payment is confirmed."}
            )

        locked_order.status = new_status
        if new_status == Order.STATUS_PAID:
            locked_order.payment_status = Order.PAYMENT_PAID
        elif (
            new_status == Order.STATUS_DELIVERED
            and locked_order.payment_method == "cash_on_delivery"
        ):
            # Cash collected upon delivery
            locked_order.payment_status = Order.PAYMENT_PAID

        locked_order.save(update_fields=["status", "payment_status", "updated_at"])

        # Sync caller instance
        order.status = locked_order.status
        order.payment_status = locked_order.payment_status
        order.updated_at = locked_order.updated_at
        return locked_order
