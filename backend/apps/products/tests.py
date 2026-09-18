from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.products.models import Category, Product

User = get_user_model()


class CategoryModelAndAPITests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email="admin@musclemax.com",
            password="AdminPass123!",
            role=User.ROLE_ADMIN,
        )
        self.customer_user = User.objects.create_user(
            email="customer@musclemax.com",
            password="CustomerPass123!",
            role=User.ROLE_CUSTOMER,
        )
        self.active_category = Category.objects.create(
            name="Proteins",
            slug="proteins",
            description="High quality protein powders",
            is_active=True,
        )
        self.inactive_category = Category.objects.create(
            name="Discontinued Pre-Workouts",
            slug="discontinued-pre-workouts",
            description="Old line",
            is_active=False,
        )
        self.categories_url = reverse("category-list")

    def test_category_creation_and_auto_slug(self):
        cat = Category.objects.create(name="Creatine Monohydrate")
        self.assertEqual(cat.slug, "creatine-monohydrate")
        self.assertTrue(cat.is_active)

    def test_duplicate_category_name_fails(self):
        with self.assertRaises(ValidationError):
            cat = Category(name="Proteins")
            cat.save()

    def test_public_can_list_active_categories_only(self):
        response = self.client.get(self.categories_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = [c["slug"] for c in response.data.get("results", response.data)]
        self.assertIn("proteins", slugs)
        self.assertNotIn("discontinued-pre-workouts", slugs)

    def test_admin_can_view_all_categories_including_inactive(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.categories_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = [c["slug"] for c in response.data.get("results", response.data)]
        self.assertIn("proteins", slugs)
        self.assertIn("discontinued-pre-workouts", slugs)

    def test_category_dual_lookup_by_id_and_slug(self):
        # By ID
        id_url = reverse("category-detail", kwargs={"pk": self.active_category.id})
        res_id = self.client.get(id_url)
        self.assertEqual(res_id.status_code, status.HTTP_200_OK)
        self.assertEqual(res_id.data["name"], "Proteins")

        # By Slug
        slug_url = reverse("category-detail", kwargs={"pk": self.active_category.slug})
        res_slug = self.client.get(slug_url)
        self.assertEqual(res_slug.status_code, status.HTTP_200_OK)
        self.assertEqual(res_slug.data["id"], self.active_category.id)

    def test_category_product_count_behavior(self):
        Product.objects.create(
            name="Active Whey",
            slug="active-whey",
            category=self.active_category,
            price=Decimal("49.99"),
            stock_quantity=10,
            is_active=True,
        )
        Product.objects.create(
            name="Hidden Draft Whey",
            slug="hidden-draft-whey",
            category=self.active_category,
            price=Decimal("39.99"),
            stock_quantity=5,
            is_active=False,
        )

        # Public user sees product_count = 1 (active only)
        slug_url = reverse("category-detail", kwargs={"pk": self.active_category.slug})
        res_public = self.client.get(slug_url)
        self.assertEqual(res_public.data["product_count"], 1)

        # Admin user sees product_count = 2 (all products)
        self.client.force_authenticate(user=self.admin_user)
        res_admin = self.client.get(slug_url)
        self.assertEqual(res_admin.data["product_count"], 2)

    def test_admin_can_create_and_delete_category(self):
        self.client.force_authenticate(user=self.admin_user)
        data = {
            "name": "Vitamins & Minerals",
            "slug": "vitamins-minerals",
            "description": "Daily essentials",
        }
        res_create = self.client.post(self.categories_url, data)
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        created_id = res_create.data["id"]

        detail_url = reverse("category-detail", kwargs={"pk": created_id})
        res_delete = self.client.delete(detail_url)
        self.assertEqual(res_delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Category.objects.filter(id=created_id).exists())

    def test_customer_cannot_modify_category(self):
        self.client.force_authenticate(user=self.customer_user)
        data = {"name": "Hacked Category"}
        res = self.client.post(self.categories_url, data)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class ProductModelAndAPITests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email="admin_prod@musclemax.com",
            password="AdminPass123!",
            role=User.ROLE_ADMIN,
        )
        self.customer_user = User.objects.create_user(
            email="customer_prod@musclemax.com",
            password="CustomerPass123!",
            role=User.ROLE_CUSTOMER,
        )
        self.category_protein = Category.objects.create(
            name="Protein",
            slug="protein",
            is_active=True,
        )
        self.category_amino = Category.objects.create(
            name="Amino Acids",
            slug="amino-acids",
            is_active=True,
        )
        self.inactive_category = Category.objects.create(
            name="Archived Category",
            slug="archived-category",
            is_active=False,
        )

        self.p1 = Product.objects.create(
            name="Gold Standard 100% Whey",
            slug="gold-standard-100-whey",
            brand="Optimum Nutrition",
            category=self.category_protein,
            price=Decimal("64.99"),
            discount_price=Decimal("54.99"),
            stock_quantity=25,
            weight="2kg",
            flavour="Double Rich Chocolate",
            specs={"servings": 74, "protein_per_serving": "24g"},
            is_active=True,
            is_featured=True,
        )
        self.p2 = Product.objects.create(
            name="Creatine Micronized",
            slug="creatine-micronized",
            brand="MuscleTech",
            category=self.category_amino,
            price=Decimal("29.99"),
            discount_price=None,
            stock_quantity=0,  # Out of stock
            weight="300g",
            flavour="Unflavoured",
            specs={"servings": 60, "creatine_per_serving": "5g"},
            is_active=True,
            is_featured=False,
        )
        self.p3_inactive = Product.objects.create(
            name="Draft Supplement",
            slug="draft-supplement",
            brand="Optimum Nutrition",
            category=self.category_protein,
            price=Decimal("19.99"),
            stock_quantity=10,
            is_active=False,
        )
        self.p4_in_inactive_cat = Product.objects.create(
            name="Archived Supplement",
            slug="archived-supplement",
            brand="OldBrand",
            category=self.inactive_category,
            price=Decimal("15.00"),
            stock_quantity=10,
            is_active=True,
        )

        self.products_url = reverse("product-list")

    def test_product_model_validation_price_and_discount(self):
        # Negative or zero price
        with self.assertRaises(ValidationError):
            p = Product(
                name="Invalid Zero Price",
                category=self.category_protein,
                price=Decimal("0.00"),
            )
            p.save()

        # Discount price higher than or equal to regular price
        with self.assertRaises(ValidationError):
            p = Product(
                name="Invalid Discount",
                category=self.category_protein,
                price=Decimal("50.00"),
                discount_price=Decimal("55.00"),
            )
            p.save()

    def test_product_properties(self):
        self.assertTrue(self.p1.in_stock)
        self.assertEqual(self.p1.effective_price, Decimal("54.99"))

        self.assertFalse(self.p2.in_stock)
        self.assertEqual(self.p2.effective_price, Decimal("29.99"))

    def test_public_user_lists_only_active_products_in_active_categories(self):
        response = self.client.get(self.products_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        slugs = [p["slug"] for p in results]

        self.assertIn("gold-standard-100-whey", slugs)
        self.assertIn("creatine-micronized", slugs)
        self.assertNotIn("draft-supplement", slugs)
        self.assertNotIn("archived-supplement", slugs)

    def test_admin_user_can_view_inactive_products(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.products_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        slugs = [p["slug"] for p in results]

        self.assertIn("gold-standard-100-whey", slugs)
        self.assertIn("draft-supplement", slugs)

    def test_product_dual_lookup_by_id_and_slug(self):
        # By ID
        res_id = self.client.get(reverse("product-detail", kwargs={"pk": self.p1.id}))
        self.assertEqual(res_id.status_code, status.HTTP_200_OK)
        self.assertEqual(res_id.data["slug"], "gold-standard-100-whey")
        self.assertEqual(res_id.data["specs"]["servings"], 74)

        # By Slug
        res_slug = self.client.get(reverse("product-detail", kwargs={"pk": self.p1.slug}))
        self.assertEqual(res_slug.status_code, status.HTTP_200_OK)
        self.assertEqual(res_slug.data["id"], self.p1.id)

    def test_product_search_filter(self):
        response = self.client.get(self.products_url, {"search": "creatine"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["slug"], "creatine-micronized")

    def test_product_filter_by_category_slug_and_id(self):
        # Filter by category slug
        res_slug = self.client.get(self.products_url, {"category": "protein"})
        self.assertEqual(res_slug.status_code, status.HTTP_200_OK)
        results_slug = res_slug.data.get("results", res_slug.data)
        self.assertEqual(len(results_slug), 1)
        self.assertEqual(results_slug[0]["slug"], "gold-standard-100-whey")

        # Filter by category numeric ID
        res_id = self.client.get(self.products_url, {"category": str(self.category_protein.id)})
        self.assertEqual(res_id.status_code, status.HTTP_200_OK)
        results_id = res_id.data.get("results", res_id.data)
        self.assertEqual(len(results_id), 1)
        self.assertEqual(results_id[0]["id"], self.p1.id)

    def test_product_filter_by_brand(self):
        response = self.client.get(self.products_url, {"brand": "Optimum Nutrition"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["slug"], "gold-standard-100-whey")

    def test_product_filter_by_in_stock(self):
        # in_stock=true
        res_in = self.client.get(self.products_url, {"in_stock": "true"})
        results_in = res_in.data.get("results", res_in.data)
        slugs_in = [p["slug"] for p in results_in]
        self.assertIn("gold-standard-100-whey", slugs_in)
        self.assertNotIn("creatine-micronized", slugs_in)

        # in_stock=false
        res_out = self.client.get(self.products_url, {"in_stock": "false"})
        results_out = res_out.data.get("results", res_out.data)
        slugs_out = [p["slug"] for p in results_out]
        self.assertIn("creatine-micronized", slugs_out)
        self.assertNotIn("gold-standard-100-whey", slugs_out)

    def test_product_filter_by_price_range(self):
        response = self.client.get(self.products_url, {"min_price": "20.00", "max_price": "40.00"})
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["slug"], "creatine-micronized")

    def test_product_ordering_by_price(self):
        # Ascending price
        res_asc = self.client.get(self.products_url, {"ordering": "price"})
        results_asc = res_asc.data.get("results", res_asc.data)
        self.assertEqual(results_asc[0]["slug"], "creatine-micronized")  # 29.99
        self.assertEqual(results_asc[1]["slug"], "gold-standard-100-whey")  # 64.99

        # Descending price
        res_desc = self.client.get(self.products_url, {"ordering": "-price"})
        results_desc = res_desc.data.get("results", res_desc.data)
        self.assertEqual(results_desc[0]["slug"], "gold-standard-100-whey")
        self.assertEqual(results_desc[1]["slug"], "creatine-micronized")

    def test_admin_create_update_delete_product(self):
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            "name": "BCAA Energy Powder",
            "slug": "bcaa-energy-powder",
            "brand": "Optimum Nutrition",
            "category": self.category_amino.id,
            "description": "Essential branched-chain amino acids",
            "price": "34.99",
            "discount_price": "29.99",
            "stock_quantity": 50,
            "weight": "280g",
            "flavour": "Watermelon",
            "specs": {"bcaa_ratio": "2:1:1"},
            "is_active": True,
            "is_featured": True,
        }

        # Create
        res_create = self.client.post(self.products_url, payload, format="json")
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        new_id = res_create.data["id"]
        self.assertEqual(res_create.data["name"], "BCAA Energy Powder")
        self.assertEqual(res_create.data["category_detail"]["name"], "Amino Acids")
        self.assertEqual(res_create.data["specs"]["bcaa_ratio"], "2:1:1")

        # Update (PATCH)
        detail_url = reverse("product-detail", kwargs={"pk": new_id})
        res_update = self.client.patch(detail_url, {"price": "32.99"}, format="json")
        self.assertEqual(res_update.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(res_update.data["price"]), Decimal("32.99"))

        # Delete
        res_delete = self.client.delete(detail_url)
        self.assertEqual(res_delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Product.objects.filter(id=new_id).exists())

    def test_serializer_validation_rejects_invalid_discount_price(self):
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            "name": "Faulty Product",
            "category": self.category_protein.id,
            "price": "20.00",
            "discount_price": "25.00",  # Invalid: discount >= price
            "stock_quantity": 10,
        }
        res = self.client.post(self.products_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("discount_price", res.data)

    def test_customer_cannot_modify_products(self):
        self.client.force_authenticate(user=self.customer_user)
        payload = {
            "name": "Unauthorized Product",
            "category": self.category_protein.id,
            "price": "20.00",
        }
        res_create = self.client.post(self.products_url, payload, format="json")
        self.assertEqual(res_create.status_code, status.HTTP_403_FORBIDDEN)

        detail_url = reverse("product-detail", kwargs={"pk": self.p1.id})
        res_patch = self.client.patch(detail_url, {"price": "1.00"}, format="json")
        self.assertEqual(res_patch.status_code, status.HTTP_403_FORBIDDEN)

        res_delete = self.client.delete(detail_url)
        self.assertEqual(res_delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_modify_products(self):
        payload = {
            "name": "Anonymous Product",
            "category": self.category_protein.id,
            "price": "20.00",
        }
        res_create = self.client.post(self.products_url, payload, format="json")
        self.assertEqual(res_create.status_code, status.HTTP_401_UNAUTHORIZED)

