from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.cart.models import Cart
from apps.cart.services import add_to_cart, get_or_create_user_cart
from apps.orders.models import Order, OrderItem
from apps.orders.services import (
    cancel_order,
    create_order_from_cart,
    update_order_status,
)
from apps.products.models import Category, Product

User = get_user_model()


class OrderModelTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ordermodel@musclemax.com",
            password="OrderPassword123!",
            first_name="Order",
            last_name="Tester",
        )
        self.category = Category.objects.create(name="Proteins", slug="proteins", is_active=True)
        self.product = Product.objects.create(
            name="Whey Isolate",
            slug="whey-isolate",
            brand="MuscleMax",
            category=self.category,
            price=Decimal("60.00"),
            discount_price=Decimal("50.00"),
            stock_quantity=30,
            is_active=True,
        )

    def test_order_creation_and_auto_number(self):
        order = Order.objects.create(
            user=self.user,
            shipping_address="123 Fitness Ave, Suite 100",
            payment_method="cash_on_delivery",
            total=Decimal("100.00"),
        )
        self.assertTrue(order.order_number.startswith("ORD-"))
        self.assertEqual(order.status, Order.STATUS_PENDING)
        self.assertEqual(order.payment_status, Order.PAYMENT_PENDING)
        self.assertTrue(order.can_cancel)
        self.assertEqual(order.items_count, 0)

    def test_order_item_snapshot_and_line_total(self):
        order = Order.objects.create(
            user=self.user,
            shipping_address="123 Fitness Ave",
            total=Decimal("150.00"),
        )
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=3,
            price_at_purchase=Decimal("50.00"),
        )

        self.assertEqual(item.product_name, "Whey Isolate")
        self.assertEqual(item.product_brand, "MuscleMax")
        self.assertEqual(item.line_total, Decimal("150.00"))
        self.assertEqual(order.items_count, 3)

        # Price snapshot resilience: change product price in catalog
        self.product.price = Decimal("80.00")
        self.product.discount_price = Decimal("75.00")
        self.product.save()

        # Order item historical price remains untouched
        item.refresh_from_db()
        self.assertEqual(item.price_at_purchase, Decimal("50.00"))
        self.assertEqual(item.line_total, Decimal("150.00"))

    def test_invalid_status_transition_raises_validation_error(self):
        order = Order.objects.create(
            user=self.user,
            shipping_address="123 Fitness Ave",
            status=Order.STATUS_PENDING,
            total=Decimal("50.00"),
        )

        # Direct transition from pending to delivered is invalid
        order.status = Order.STATUS_DELIVERED
        with self.assertRaises(ValidationError):
            order.save()


class CheckoutServiceTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="checkoutuser@musclemax.com",
            password="CheckoutPassword123!",
        )
        self.category = Category.objects.create(name="Supplements", slug="supplements", is_active=True)
        self.product1 = Product.objects.create(
            name="Creatine Powder",
            slug="creatine-powder",
            brand="MuscleMax",
            category=self.category,
            price=Decimal("30.00"),
            discount_price=Decimal("25.00"),
            stock_quantity=10,
            is_active=True,
        )
        self.product2 = Product.objects.create(
            name="Pre-Workout Surge",
            slug="pre-workout-surge",
            brand="MuscleMax",
            category=self.category,
            price=Decimal("40.00"),
            discount_price=None,
            stock_quantity=5,
            is_active=True,
        )

    def test_successful_checkout_from_cart(self):
        cart = get_or_create_user_cart(self.user)
        add_to_cart(cart, self.product1.id, quantity=2)  # 2 * 25.00 = 50.00
        add_to_cart(cart, self.product2.id, quantity=1)  # 1 * 40.00 = 40.00

        order = create_order_from_cart(
            user=self.user,
            shipping_address="742 Evergreen Terrace, Springfield",
            payment_method="card",
        )

        self.assertEqual(order.user, self.user)
        self.assertEqual(order.total, Decimal("90.00"))
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.status, Order.STATUS_PENDING)

        # Inventory correctly deducted
        self.product1.refresh_from_db()
        self.product2.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 8)  # 10 - 2
        self.assertEqual(self.product2.stock_quantity, 4)  # 5 - 1

        # Cart cleared after successful checkout
        cart.refresh_from_db()
        self.assertEqual(cart.items.count(), 0)

    def test_empty_cart_checkout_rejected(self):
        with self.assertRaises(ValidationError):
            create_order_from_cart(
                user=self.user,
                shipping_address="123 Nowhere St",
            )

    def test_insufficient_stock_checkout_rolls_back_completely(self):
        cart = get_or_create_user_cart(self.user)
        add_to_cart(cart, self.product1.id, quantity=2)

        # Another user buys out stock in between
        self.product1.stock_quantity = 1
        self.product1.save()

        with self.assertRaises(ValidationError):
            create_order_from_cart(
                user=self.user,
                shipping_address="123 Fitness Ave",
            )

        # Assert no order was created
        self.assertEqual(Order.objects.count(), 0)
        # Assert stock was not reduced
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 1)
        # Assert cart was preserved
        self.assertEqual(cart.items.count(), 1)

    def test_inactive_product_checkout_rejected(self):
        cart = get_or_create_user_cart(self.user)
        add_to_cart(cart, self.product1.id, quantity=1)

        # Product deactivated before checkout
        self.product1.is_active = False
        self.product1.save()

        with self.assertRaises(ValidationError):
            create_order_from_cart(user=self.user, shipping_address="123 Fitness Ave")

        # Cart preserved
        self.assertEqual(cart.items.count(), 1)
        self.assertEqual(Order.objects.count(), 0)

    def test_order_cancellation_restores_inventory(self):
        cart = get_or_create_user_cart(self.user)
        add_to_cart(cart, self.product1.id, quantity=4)

        order = create_order_from_cart(self.user, shipping_address="123 Test St")
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 6)  # 10 - 4

        # Cancel order
        cancelled_order = cancel_order(order, self.user)
        self.assertEqual(cancelled_order.status, Order.STATUS_CANCELLED)

        # Stock is restored
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 10)

        # Cannot cancel again
        with self.assertRaises(ValidationError):
            cancel_order(cancelled_order, self.user)

    def test_admin_order_status_progression(self):
        cart = get_or_create_user_cart(self.user)
        add_to_cart(cart, self.product1.id, quantity=1)
        order = create_order_from_cart(self.user, shipping_address="123 Test St")

        # Pending -> Paid
        order = update_order_status(order, Order.STATUS_PAID, is_admin=True)
        self.assertEqual(order.status, Order.STATUS_PAID)
        self.assertEqual(order.payment_status, Order.PAYMENT_PAID)

        # Paid -> Shipped
        order = update_order_status(order, Order.STATUS_SHIPPED, is_admin=True)
        self.assertEqual(order.status, Order.STATUS_SHIPPED)

        # Shipped -> Delivered
        order = update_order_status(order, Order.STATUS_DELIVERED, is_admin=True)
        self.assertEqual(order.status, Order.STATUS_DELIVERED)

        # Terminal state: cannot transition delivered back to pending
        with self.assertRaises(ValidationError):
            update_order_status(order, Order.STATUS_PENDING, is_admin=True)


class OrderAPITests(APITestCase):
    def setUp(self):
        self.customer_a = User.objects.create_user(
            email="customer_a@musclemax.com",
            password="CustomerAPass123!",
            first_name="Customer",
            last_name="A",
            role=User.ROLE_CUSTOMER,
        )
        self.customer_b = User.objects.create_user(
            email="customer_b@musclemax.com",
            password="CustomerBPass123!",
            first_name="Customer",
            last_name="B",
            role=User.ROLE_CUSTOMER,
        )
        self.admin_user = User.objects.create_superuser(
            email="admin_orders@musclemax.com",
            password="AdminPass123!",
            first_name="Super",
            last_name="Admin",
            role=User.ROLE_ADMIN,
        )

        self.category = Category.objects.create(name="Whey", slug="whey", is_active=True)
        self.product = Product.objects.create(
            name="100% Whey Gold",
            slug="100-whey-gold",
            category=self.category,
            price=Decimal("50.00"),
            stock_quantity=20,
            is_active=True,
        )

        self.orders_url = reverse("order-list")

    def test_anonymous_order_access_rejected(self):
        # List orders -> 401
        res = self.client.get(self.orders_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # Create order -> 401
        res = self.client.post(self.orders_url, {"shipping_address": "123 St"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_create_and_retrieve_order(self):
        # Populate Customer A's cart
        cart_a = get_or_create_user_cart(self.customer_a)
        add_to_cart(cart_a, self.product.id, quantity=2)

        self.client.force_authenticate(user=self.customer_a)
        payload = {
            "shipping_address": "456 Muscle Way, Venice Beach, CA",
            "payment_method": "cash_on_delivery",
        }
        res_create = self.client.post(self.orders_url, payload, format="json")
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(res_create.data["total"]), Decimal("100.00"))
        self.assertEqual(len(res_create.data["items"]), 1)
        self.assertEqual(res_create.data["status"], "pending")

        order_id = res_create.data["id"]
        order_number = res_create.data["order_number"]

        # Retrieve by numeric ID
        detail_id_url = reverse("order-detail", kwargs={"pk": order_id})
        res_detail_id = self.client.get(detail_id_url)
        self.assertEqual(res_detail_id.status_code, status.HTTP_200_OK)
        self.assertEqual(res_detail_id.data["id"], order_id)

        # Retrieve by order_number string
        detail_num_url = reverse("order-detail", kwargs={"pk": order_number})
        res_detail_num = self.client.get(detail_num_url)
        self.assertEqual(res_detail_num.status_code, status.HTTP_200_OK)
        self.assertEqual(res_detail_num.data["id"], order_id)

    def test_cross_user_idor_protection(self):
        # Create an order for Customer A
        cart_a = get_or_create_user_cart(self.customer_a)
        add_to_cart(cart_a, self.product.id, quantity=1)
        order_a = create_order_from_cart(self.customer_a, shipping_address="Customer A Address")

        # Customer B tries to view, patch, or cancel Customer A's order
        self.client.force_authenticate(user=self.customer_b)

        detail_url = reverse("order-detail", kwargs={"pk": order_a.id})
        res_get = self.client.get(detail_url)
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)

        cancel_url = reverse("order-cancel", kwargs={"pk": order_a.id})
        res_cancel = self.client.post(cancel_url)
        self.assertEqual(res_cancel.status_code, status.HTTP_404_NOT_FOUND)

        res_patch = self.client.patch(detail_url, {"status": "cancelled"}, format="json")
        self.assertEqual(res_patch.status_code, status.HTTP_404_NOT_FOUND)

    def test_customer_can_cancel_own_order(self):
        cart_a = get_or_create_user_cart(self.customer_a)
        add_to_cart(cart_a, self.product.id, quantity=2)
        order_a = create_order_from_cart(self.customer_a, shipping_address="Customer A Address")

        self.client.force_authenticate(user=self.customer_a)
        cancel_url = reverse("order-cancel", kwargs={"pk": order_a.id})
        res_cancel = self.client.post(cancel_url)
        self.assertEqual(res_cancel.status_code, status.HTTP_200_OK)
        self.assertEqual(res_cancel.data["order"]["status"], "cancelled")

        # Verify stock was restored
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)

    def test_customer_cannot_patch_order_status_even_to_cancelled(self):
        """Verify customers cannot change order status through PATCH under any circumstances."""
        cart_a = get_or_create_user_cart(self.customer_a)
        add_to_cart(cart_a, self.product.id, quantity=1)
        order_a = create_order_from_cart(self.customer_a, shipping_address="Customer A Address")

        self.client.force_authenticate(user=self.customer_a)
        detail_url = reverse("order-detail", kwargs={"pk": order_a.id})

        # Customer attempting to mark order 'shipped' via PATCH -> 403 Forbidden
        res_patch_ship = self.client.patch(detail_url, {"status": "shipped"}, format="json")
        self.assertEqual(res_patch_ship.status_code, status.HTTP_403_FORBIDDEN)

        # Customer attempting to mark order 'cancelled' via PATCH -> 403 Forbidden
        res_patch_cancel = self.client.patch(detail_url, {"status": "cancelled"}, format="json")
        self.assertEqual(res_patch_cancel.status_code, status.HTTP_403_FORBIDDEN)

        # Customer attempting to mark order 'paid' via PATCH -> 403 Forbidden
        res_patch_paid = self.client.patch(detail_url, {"status": "paid"}, format="json")
        self.assertEqual(res_patch_paid.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_manage_all_orders_and_status(self):
        cart_a = get_or_create_user_cart(self.customer_a)
        add_to_cart(cart_a, self.product.id, quantity=1)
        order_a = create_order_from_cart(
            self.customer_a,
            shipping_address="Customer A Address",
            payment_method="card",
        )

        # Admin logs in
        self.client.force_authenticate(user=self.admin_user)

        # Admin can view Customer A's order
        detail_url = reverse("order-detail", kwargs={"pk": order_a.id})
        res_get = self.client.get(detail_url)
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertEqual(res_get.data["id"], order_a.id)

        # Admin updates status to 'paid'
        res_paid = self.client.patch(detail_url, {"status": "paid"}, format="json")
        self.assertEqual(res_paid.status_code, status.HTTP_200_OK)
        self.assertEqual(res_paid.data["status"], "paid")

        # Admin updates status to 'shipped'
        res_shipped = self.client.patch(detail_url, {"status": "shipped"}, format="json")
        self.assertEqual(res_shipped.status_code, status.HTTP_200_OK)
        self.assertEqual(res_shipped.data["status"], "shipped")

        # Admin attempts invalid status transition (shipped -> pending) -> 400 Bad Request
        res_invalid = self.client.patch(detail_url, {"status": "pending"}, format="json")
        self.assertEqual(res_invalid.status_code, status.HTTP_400_BAD_REQUEST)

    def test_order_cancellation_idempotence_and_single_stock_restoration(self):
        """Verify order cancellation is idempotent and stock is restored only once."""
        cart_a = get_or_create_user_cart(self.customer_a)
        add_to_cart(cart_a, self.product.id, quantity=4)
        order_a = create_order_from_cart(self.customer_a, shipping_address="Customer A Address")

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 16)  # 20 - 4

        # First cancellation via service
        cancel_order(order_a, self.customer_a)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)  # Restored

        # Second cancellation attempt via service raises ValidationError
        with self.assertRaises(ValidationError):
            cancel_order(order_a, self.customer_a)

        # Stock is NOT restored a second time
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)

        # Second cancellation attempt via API endpoint returns 400 Bad Request
        self.client.force_authenticate(user=self.customer_a)
        cancel_url = reverse("order-cancel", kwargs={"pk": order_a.id})
        res_cancel = self.client.post(cancel_url)
        self.assertEqual(res_cancel.status_code, status.HTTP_400_BAD_REQUEST)

        # Stock remains strictly 20
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)

    def test_only_eligible_orders_can_be_cancelled(self):
        """Verify only eligible orders (pending or paid) can be cancelled."""
        cart_a = get_or_create_user_cart(self.customer_a)
        add_to_cart(cart_a, self.product.id, quantity=1)
        order = create_order_from_cart(self.customer_a, shipping_address="Customer A Address")

        # 1. Pending: can be cancelled
        self.assertTrue(order.can_cancel)

        # 2. Paid: can be cancelled
        order = update_order_status(order, Order.STATUS_PAID, is_admin=True)
        self.assertTrue(order.can_cancel)

        # 3. Shipped: cannot be cancelled
        order = update_order_status(order, Order.STATUS_SHIPPED, is_admin=True)
        self.assertFalse(order.can_cancel)
        with self.assertRaises(ValidationError):
            cancel_order(order, self.customer_a)

        # API cancellation also rejected
        self.client.force_authenticate(user=self.customer_a)
        cancel_url = reverse("order-cancel", kwargs={"pk": order.id})
        res_cancel = self.client.post(cancel_url)
        self.assertEqual(res_cancel.status_code, status.HTTP_400_BAD_REQUEST)

        # 4. Delivered: cannot be cancelled
        order = update_order_status(order, Order.STATUS_DELIVERED, is_admin=True)
        self.assertFalse(order.can_cancel)
        with self.assertRaises(ValidationError):
            cancel_order(order, self.customer_a)

    def test_admin_cannot_assign_invalid_status_transitions(self):
        """Verify admins cannot assign invalid status transitions."""
        cart_a = get_or_create_user_cart(self.customer_a)
        add_to_cart(cart_a, self.product.id, quantity=1)
        order = create_order_from_cart(
            self.customer_a,
            shipping_address="Customer A Address",
            payment_method="card",
        )

        self.client.force_authenticate(user=self.admin_user)
        detail_url = reverse("order-detail", kwargs={"pk": order.id})

        # Pending -> Delivered invalid
        res = self.client.patch(detail_url, {"status": "delivered"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Admin updates status to 'paid'
        res_paid = self.client.patch(detail_url, {"status": "paid"}, format="json")
        self.assertEqual(res_paid.status_code, status.HTTP_200_OK)
        self.assertEqual(res_paid.data["status"], "paid")
        # Transition pending -> paid (valid)
        res = self.client.patch(detail_url, {"status": "paid"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Admin updates status to 'shipped'
        res_shipped = self.client.patch(detail_url, {"status": "shipped"}, format="json")
        self.assertEqual(res_shipped.status_code, status.HTTP_200_OK)
        self.assertEqual(res_shipped.data["status"], "shipped")
        # Paid -> Pending invalid (backwards)
        res = self.client.patch(detail_url, {"status": "pending"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Admin attempts invalid status transition (shipped -> pending) -> 400 Bad Request
        res_invalid = self.client.patch(detail_url, {"status": "pending"}, format="json")
        self.assertEqual(res_invalid.status_code, status.HTTP_400_BAD_REQUEST)
        # Transition paid -> shipped (valid)
        res = self.client.patch(detail_url, {"status": "shipped"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Shipped -> Cancelled invalid (cannot cancel shipped order)
        res = self.client.patch(detail_url, {"status": "cancelled"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Transition shipped -> delivered (valid)
        res = self.client.patch(detail_url, {"status": "delivered"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Delivered is terminal
        res = self.client.patch(detail_url, {"status": "pending"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_payment_status_not_falsely_marked_as_paid(self):
        """Verify payment status is not falsely marked as paid without payment confirmation."""
        # 1. COD checkout starts as pending payment
        cart_a = get_or_create_user_cart(self.customer_a)
        add_to_cart(cart_a, self.product.id, quantity=1)
        cod_order = create_order_from_cart(
            self.customer_a,
            shipping_address="COD Address",
            payment_method="cash_on_delivery",
        )
        self.assertEqual(cod_order.payment_status, Order.PAYMENT_PENDING)

        # COD order shipped: payment status is STILL pending
        cod_order = update_order_status(cod_order, Order.STATUS_SHIPPED, is_admin=True)
        self.assertEqual(cod_order.status, Order.STATUS_SHIPPED)
        self.assertEqual(cod_order.payment_status, Order.PAYMENT_PENDING)

        # COD order delivered: payment status transitions to paid upon collection
        cod_order = update_order_status(cod_order, Order.STATUS_DELIVERED, is_admin=True)
        self.assertEqual(cod_order.status, Order.STATUS_DELIVERED)
        self.assertEqual(cod_order.payment_status, Order.PAYMENT_PAID)

        # 2. Prepaid checkout (card): cannot ship until payment is confirmed
        cart_b = get_or_create_user_cart(self.customer_b)
        add_to_cart(cart_b, self.product.id, quantity=1)
        prepaid_order = create_order_from_cart(
            self.customer_b,
            shipping_address="Prepaid Address",
            payment_method="card",
        )
        self.assertEqual(prepaid_order.payment_status, Order.PAYMENT_PENDING)

        # Attempting to ship prepaid order without payment confirmation raises ValidationError
        with self.assertRaises(ValidationError):
            update_order_status(prepaid_order, Order.STATUS_SHIPPED, is_admin=True)

        # Confirmed payment -> paid
        prepaid_order = update_order_status(prepaid_order, Order.STATUS_PAID, is_admin=True)
        self.assertEqual(prepaid_order.payment_status, Order.PAYMENT_PAID)

        # Now can be shipped
        prepaid_order = update_order_status(prepaid_order, Order.STATUS_SHIPPED, is_admin=True)
        self.assertEqual(prepaid_order.status, Order.STATUS_SHIPPED)

    def test_concurrent_checkout_cannot_oversell_stock(self):
        """Verify simultaneous checkouts cannot oversell stock when quantity is scarce."""
        # Product has only 1 in stock
        scarce_product = Product.objects.create(
            name="Limited Edition Whey",
            slug="limited-edition-whey",
            category=self.category,
            price=Decimal("99.00"),
            stock_quantity=1,
            is_active=True,
        )

        # Both Customer A and Customer B add 1 unit to cart
        cart_a = get_or_create_user_cart(self.customer_a)
        add_to_cart(cart_a, scarce_product.id, quantity=1)

        cart_b = get_or_create_user_cart(self.customer_b)
        add_to_cart(cart_b, scarce_product.id, quantity=1)

        # Customer A checks out first
        order_a = create_order_from_cart(self.customer_a, shipping_address="Customer A Address")
        self.assertIsNotNone(order_a)

        scarce_product.refresh_from_db()
        self.assertEqual(scarce_product.stock_quantity, 0)

        # Customer B attempts checkout immediately after
        with self.assertRaises(ValidationError):
            create_order_from_cart(self.customer_b, shipping_address="Customer B Address")

        # Verify stock did not drop below 0
        scarce_product.refresh_from_db()
        self.assertEqual(scarce_product.stock_quantity, 0)

        # Verify Customer B's cart is preserved
        cart_b.refresh_from_db()
        self.assertEqual(cart_b.items.count(), 1)


