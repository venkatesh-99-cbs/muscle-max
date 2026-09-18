from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.cart.models import Cart, CartItem
from apps.products.models import Product


def get_or_create_user_cart(user) -> Cart:
    """
    Safely retrieves or initializes a customer cart.
    Handles concurrency race conditions for the OneToOne relationship using
    atomic transactions and IntegrityError fallbacks.
    """
    try:
        return Cart.objects.get(user=user)
    except Cart.DoesNotExist:
        try:
            with transaction.atomic():
                cart, _ = Cart.objects.get_or_create(user=user)
                return cart
        except IntegrityError:
            return Cart.objects.get(user=user)


def resolve_product(product_identifier) -> Product:
    """
    Resolves product by numeric ID or slug string.
    Raises ValidationError if product does not exist.
    """
    ident_str = str(product_identifier).strip()
    try:
        if ident_str.isdigit():
            return Product.objects.select_related("category").get(id=int(ident_str))
        return Product.objects.select_related("category").get(slug=ident_str)
    except Product.DoesNotExist:
        raise ValidationError({"product": f"Product '{product_identifier}' does not exist."})


def add_to_cart(cart: Cart, product_identifier, quantity: int = 1) -> CartItem:
    """
    Adds a product to the user's cart or increments quantity if already present.
    Uses database row-locking (select_for_update) inside an atomic transaction
    to prevent stock overselling under concurrent requests.
    """
    if quantity <= 0:
        raise ValidationError({"quantity": "Quantity must be greater than zero."})

    with transaction.atomic():
        # First resolve product ID without lock to establish identity
        temp_product = resolve_product(product_identifier)

        # Lock the Product record to guarantee atomic stock evaluation
        product = (
            Product.objects.select_for_update()
            .select_related("category")
            .get(id=temp_product.id)
        )

        if not product.is_active:
            raise ValidationError({"product": "This product is currently inactive and cannot be added to cart."})
        if not product.category.is_active:
            raise ValidationError({"product": "This product belongs to an inactive category and cannot be added."})

        # Lock CartItem if it already exists
        cart_item = (
            CartItem.objects.select_for_update()
            .filter(cart=cart, product=product)
            .first()
        )

        if cart_item:
            new_quantity = cart_item.quantity + quantity
        else:
            new_quantity = quantity

        if new_quantity > product.stock_quantity:
            available = product.stock_quantity - (cart_item.quantity if cart_item else 0)
            raise ValidationError(
                {
                    "quantity": (
                        f"Cannot add {quantity} units. Current in cart: {cart_item.quantity if cart_item else 0}. "
                        f"Available in stock: {product.stock_quantity} (remaining addable: {max(0, available)})."
                    )
                }
            )

        if cart_item:
            cart_item.quantity = new_quantity
            cart_item.save()
        else:
            cart_item = CartItem.objects.create(cart=cart, product=product, quantity=new_quantity)

        cart.save(update_fields=["updated_at"])
        return cart_item


def update_cart_item_quantity(cart: Cart, item_id: int, quantity: int) -> CartItem:
    """
    Updates the quantity of an item within the user's cart.
    Uses select_for_update on both CartItem and Product inside an atomic transaction.
    """
    if quantity <= 0:
        raise ValidationError({"quantity": "Quantity must be at least 1."})

    with transaction.atomic():
        try:
            cart_item = (
                CartItem.objects.select_for_update()
                .select_related("product")
                .get(cart=cart, id=item_id)
            )
        except CartItem.DoesNotExist:
            raise ValidationError({"item": "Cart item not found in your cart."})

        product = Product.objects.select_for_update().get(id=cart_item.product_id)

        if not product.is_active:
            raise ValidationError({"product": "Product is no longer active."})
        if not product.category.is_active:
            raise ValidationError({"product": "Product's category is no longer active."})

        if quantity > product.stock_quantity:
            raise ValidationError(
                {"quantity": f"Requested quantity ({quantity}) exceeds available stock ({product.stock_quantity})."}
            )

        cart_item.quantity = quantity
        cart_item.save()

        cart.save(update_fields=["updated_at"])
        return cart_item


def remove_cart_item(cart: Cart, item_id: int) -> bool:
    """
    Removes an item from the user's cart.
    Scoped strictly to cart to prevent IDOR attacks.
    """
    deleted_count, _ = cart.items.filter(id=item_id).delete()
    if deleted_count > 0:
        cart.save(update_fields=["updated_at"])
        return True
    return False


def clear_cart(cart: Cart) -> int:
    """
    Clears all items from the user's cart.
    """
    count, _ = cart.items.all().delete()
    cart.save(update_fields=["updated_at"])
    return count
