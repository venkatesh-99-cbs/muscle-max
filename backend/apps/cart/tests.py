from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.cart.models import Cart, CartItem
from apps.cart.services import (
    add_to_cart,
    clear_cart,
    get_or_create_user_cart,
    remove_cart_item,
    update_cart_item_quantity,
)
from apps.products.models import Category, Product

User = get_user_model()


class CartModelTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="cartuser@musclemax.com",
            password="CartPassword123!",
            first_name="Cart",
            last_name="Tester",
        )
        self.category = Category.objects.create(
            name="Supplements",
            slug="supplements",
            is_active=True,
        )
        self.product = Product.objects.create(
            name="Whey Isolate",
            slug="whey-isolate",
            category=self.category,
            price=Decimal("50.00"),
            discount_price=Decimal("45.00"),
            stock_quantity=20,
            is_active=True,
        )

    def test_cart_creation_and_one_to_one(self):
        cart = Cart.objects.create(user=self.user)
        self.assertEqual(str(cart), f"Cart ({self.user.email})")
        self.assertTrue(cart.is_empty)
        self.assertEqual(cart.total_items, 0)
        self.assertEqual(cart.subtotal, Decimal("0.00"))

        # Attempting to create a second cart for the same user must fail OneToOne unique constraint
        with self.assertRaises(IntegrityError):
            Cart.objects.create(user=self.user)

    def test_cart_item_calculations_with_effective_price(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=3,
        )

        self.assertEqual(item.unit_price, Decimal("50.00"))
        # Effective price should use valid discount_price (45.00)
        self.assertEqual(item.effective_price, Decimal("45.00"))
        # Line total = 45.00 * 3 = 135.00
        self.assertEqual(item.line_total, Decimal("135.00"))

        # Cart properties
        self.assertFalse(cart.is_empty)
        self.assertEqual(cart.total_items, 3)
        self.assertEqual(cart.subtotal, Decimal("135.00"))

    def test_dynamic_price_and_discount_changes(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=2,
        )
        self.assertEqual(cart.subtotal, Decimal("90.00"))

        # Change product discount price in database
        self.product.discount_price = Decimal("40.00")
        self.product.save()

        # Item and Cart subtotal dynamically re-evaluate
        self.assertEqual(item.effective_price, Decimal("40.00"))
        self.assertEqual(item.line_total, Decimal("80.00"))
        self.assertEqual(cart.subtotal, Decimal("80.00"))

        # Remove discount price (None)
        self.product.discount_price = None
        self.product.save()

        self.assertEqual(item.effective_price, Decimal("50.00"))
        self.assertEqual(item.line_total, Decimal("100.00"))
        self.assertEqual(cart.subtotal, Decimal("100.00"))

    def test_unique_cart_product_constraint(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)

        # Model validation via save() raises ValidationError
        with self.assertRaises(ValidationError):
            CartItem.objects.create(cart=cart, product=self.product, quantity=2)

        # Database constraint via bulk_create (bypassing full_clean) raises IntegrityError
        with self.assertRaises(IntegrityError):
            CartItem.objects.bulk_create([
                CartItem(cart=cart, product=self.product, quantity=2)
            ])

    def test_cart_item_quantity_validation(self):
        cart = Cart.objects.create(user=self.user)
        # Quantity <= 0 must fail validation
        with self.assertRaises(ValidationError):
            item = CartItem(cart=cart, product=self.product, quantity=0)
            item.save()

        # Quantity > stock must fail validation
        with self.assertRaises(ValidationError):
            item = CartItem(cart=cart, product=self.product, quantity=999)
            item.save()

    def test_product_deletion_protected(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)

        # Attempting to hard-delete product in active cart must raise ProtectedError
        from django.db.models.deletion import ProtectedError
        with self.assertRaises(ProtectedError):
            self.product.delete()

    def test_existing_cart_items_removable_if_product_becomes_inactive(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(cart=cart, product=self.product, quantity=2)

        # Product later becomes inactive
        self.product.is_active = False
        self.product.save()

        # Item can still be removed cleanly
        removed = remove_cart_item(cart, item.id)
        self.assertTrue(removed)
        self.assertEqual(cart.items.count(), 0)


class CartServiceTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="serviceuser@musclemax.com",
            password="ServicePassword123!",
        )
        self.category = Category.objects.create(name="Energy", slug="energy", is_active=True)
        self.product = Product.objects.create(
            name="Caffeine Boost",
            slug="caffeine-boost",
            category=self.category,
            price=Decimal("20.00"),
            stock_quantity=15,
            is_active=True,
        )

    def test_get_or_create_cart_race_condition_handling(self):
        # Normal creation
        cart = get_or_create_user_cart(self.user)
        self.assertIsNotNone(cart.id)

        # Simulate concurrent IntegrityError on get_or_create
        with patch.object(Cart.objects, "get_or_create", side_effect=IntegrityError("Duplicate key")):
            recovered_cart = get_or_create_user_cart(self.user)
            self.assertEqual(recovered_cart.id, cart.id)

    def test_add_to_cart_increments_existing_quantity(self):
        cart = get_or_create_user_cart(self.user)
        item1 = add_to_cart(cart, self.product.id, quantity=2)
        self.assertEqual(item1.quantity, 2)
        self.assertEqual(cart.items.count(), 1)

        # Add again -> increments existing item
        item2 = add_to_cart(cart, self.product.slug, quantity=3)
        self.assertEqual(item2.id, item1.id)
        self.assertEqual(item2.quantity, 5)
        self.assertEqual(cart.items.count(), 1)

    def test_add_to_cart_exceeding_stock_rolls_back(self):
        cart = get_or_create_user_cart(self.user)
        add_to_cart(cart, self.product.id, quantity=10)

        # Adding 10 more exceeds available stock (15)
        with self.assertRaises(ValidationError):
            add_to_cart(cart, self.product.id, quantity=10)

        # Verify quantity remained unchanged at 10
        item = cart.items.get(product=self.product)
        self.assertEqual(item.quantity, 10)

    def test_add_inactive_product_or_inactive_category_fails(self):
        cart = get_or_create_user_cart(self.user)

        # Inactive product
        self.product.is_active = False
        self.product.save()
        with self.assertRaises(ValidationError):
            add_to_cart(cart, self.product.id, quantity=1)

        # Active product in inactive category
        self.product.is_active = True
        self.product.save()
        self.category.is_active = False
        self.category.save()
        with self.assertRaises(ValidationError):
            add_to_cart(cart, self.product.id, quantity=1)

    def test_clear_cart_service(self):
        cart = get_or_create_user_cart(self.user)
        add_to_cart(cart, self.product.id, quantity=2)
        self.assertEqual(cart.items.count(), 1)

        deleted = clear_cart(cart)
        self.assertEqual(deleted, 1)
        self.assertEqual(cart.items.count(), 0)


class CartAPITests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            email="user_a@musclemax.com",
            password="UserAPassword123!",
            first_name="User",
            last_name="A",
        )
        self.user_b = User.objects.create_user(
            email="user_b@musclemax.com",
            password="UserBPassword123!",
            first_name="User",
            last_name="B",
        )
        self.category = Category.objects.create(name="Vitamins", slug="vitamins", is_active=True)
        self.product_1 = Product.objects.create(
            name="Daily Multi",
            slug="daily-multi",
            category=self.category,
            price=Decimal("30.00"),
            discount_price=Decimal("25.00"),
            stock_quantity=50,
            is_active=True,
        )
        self.product_2 = Product.objects.create(
            name="Fish Oil",
            slug="fish-oil",
            category=self.category,
            price=Decimal("20.00"),
            stock_quantity=10,
            is_active=True,
        )

        self.cart_url = reverse("cart-detail")
        self.cart_items_url = reverse("cart-items")
        self.cart_clear_url = reverse("cart-clear")

    def test_anonymous_access_rejected(self):
        # GET cart -> 401
        res = self.client.get(self.cart_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # POST item -> 401
        res = self.client.post(self.cart_items_url, {"product": self.product_1.id, "quantity": 1})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # Clear -> 401
        res = self.client.post(self.cart_clear_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_empty_cart(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(self.cart_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_items"], 0)
        self.assertEqual(Decimal(response.data["subtotal"]), Decimal("0.00"))
        self.assertEqual(response.data["items"], [])

    def test_add_product_by_id_and_slug(self):
        self.client.force_authenticate(user=self.user_a)

        # Add by ID
        res_id = self.client.post(
            self.cart_items_url,
            {"product": self.product_1.id, "quantity": 2},
            format="json",
        )
        self.assertEqual(res_id.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_id.data["quantity"], 2)
        self.assertEqual(Decimal(res_id.data["effective_price"]), Decimal("25.00"))
        self.assertEqual(Decimal(res_id.data["line_total"]), Decimal("50.00"))

        # Add by Slug
        res_slug = self.client.post(
            self.cart_items_url,
            {"product": self.product_2.slug, "quantity": 1},
            format="json",
        )
        self.assertEqual(res_slug.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_slug.data["quantity"], 1)
        self.assertEqual(Decimal(res_slug.data["line_total"]), Decimal("20.00"))

        # Check cart subtotal: 50.00 + 20.00 = 70.00, total_items = 3
        res_cart = self.client.get(self.cart_url)
        self.assertEqual(res_cart.status_code, status.HTTP_200_OK)
        self.assertEqual(res_cart.data["total_items"], 3)
        self.assertEqual(Decimal(res_cart.data["subtotal"]), Decimal("70.00"))

    def test_add_existing_product_increases_quantity(self):
        self.client.force_authenticate(user=self.user_a)

        self.client.post(self.cart_items_url, {"product": self.product_1.id, "quantity": 1}, format="json")
        res_second = self.client.post(
            self.cart_items_url,
            {"product": self.product_1.id, "quantity": 3},
            format="json",
        )
        self.assertEqual(res_second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_second.data["quantity"], 4)

        res_cart = self.client.get(self.cart_url)
        self.assertEqual(len(res_cart.data["items"]), 1)
        self.assertEqual(res_cart.data["total_items"], 4)

    def test_patch_quantity(self):
        self.client.force_authenticate(user=self.user_a)
        res_add = self.client.post(
            self.cart_items_url,
            {"product": self.product_1.id, "quantity": 1},
            format="json",
        )
        item_id = res_add.data["id"]

        detail_url = reverse("cart-item-detail", kwargs={"pk": item_id})
        res_patch = self.client.patch(detail_url, {"quantity": 5}, format="json")
        self.assertEqual(res_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(res_patch.data["quantity"], 5)
        self.assertEqual(Decimal(res_patch.data["line_total"]), Decimal("125.00"))

    def test_delete_cart_item(self):
        self.client.force_authenticate(user=self.user_a)
        res_add = self.client.post(
            self.cart_items_url,
            {"product": self.product_1.id, "quantity": 2},
            format="json",
        )
        item_id = res_add.data["id"]

        detail_url = reverse("cart-item-detail", kwargs={"pk": item_id})
        res_del = self.client.delete(detail_url)
        self.assertEqual(res_del.status_code, status.HTTP_204_NO_CONTENT)

        # Verify cart is empty
        res_cart = self.client.get(self.cart_url)
        self.assertEqual(res_cart.data["total_items"], 0)

    def test_clear_cart_endpoint(self):
        self.client.force_authenticate(user=self.user_a)
        self.client.post(self.cart_items_url, {"product": self.product_1.id, "quantity": 2}, format="json")
        self.client.post(self.cart_items_url, {"product": self.product_2.id, "quantity": 1}, format="json")

        res_clear = self.client.post(self.cart_clear_url)
        self.assertEqual(res_clear.status_code, status.HTTP_200_OK)

        res_cart = self.client.get(self.cart_url)
        self.assertEqual(res_cart.data["total_items"], 0)
        self.assertEqual(len(res_cart.data["items"]), 0)

    def test_validation_errors_quantity_and_stock(self):
        self.client.force_authenticate(user=self.user_a)

        # Quantity 0
        res_zero = self.client.post(
            self.cart_items_url,
            {"product": self.product_1.id, "quantity": 0},
            format="json",
        )
        self.assertEqual(res_zero.status_code, status.HTTP_400_BAD_REQUEST)

        # Negative quantity
        res_neg = self.client.post(
            self.cart_items_url,
            {"product": self.product_1.id, "quantity": -5},
            format="json",
        )
        self.assertEqual(res_neg.status_code, status.HTTP_400_BAD_REQUEST)

        # Exceeding stock
        res_stock = self.client.post(
            self.cart_items_url,
            {"product": self.product_2.id, "quantity": 11},  # Stock is 10
            format="json",
        )
        self.assertEqual(res_stock.status_code, status.HTTP_400_BAD_REQUEST)

        # Non-existent product
        res_notfound = self.client.post(
            self.cart_items_url,
            {"product": 9999, "quantity": 1},
            format="json",
        )
        self.assertEqual(res_notfound.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cross_user_idor_protection(self):
        # User A adds an item to their cart
        self.client.force_authenticate(user=self.user_a)
        res_a = self.client.post(
            self.cart_items_url,
            {"product": self.product_1.id, "quantity": 1},
            format="json",
        )
        item_a_id = res_a.data["id"]

        # User B attempts to access, modify, or delete User A's item
        self.client.force_authenticate(user=self.user_b)
        detail_url = reverse("cart-item-detail", kwargs={"pk": item_a_id})

        # PATCH attempt by User B
        res_patch = self.client.patch(detail_url, {"quantity": 10}, format="json")
        self.assertEqual(res_patch.status_code, status.HTTP_400_BAD_REQUEST)

        # DELETE attempt by User B -> 404 Not Found
        res_delete = self.client.delete(detail_url)
        self.assertEqual(res_delete.status_code, status.HTTP_404_NOT_FOUND)

        # Verify User A's item is untouched
        self.client.force_authenticate(user=self.user_a)
        res_cart_a = self.client.get(self.cart_url)
        self.assertEqual(res_cart_a.data["total_items"], 1)
