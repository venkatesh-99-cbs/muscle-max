from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class UserModelTests(APITestCase):
    def test_create_user_with_email_successful(self):
        email = "test@musclemax.com"
        password = "SecurePassword123!"
        user = User.objects.create_user(email=email, password=password, first_name="John", last_name="Doe")
        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))
        self.assertEqual(user.role, User.ROLE_CUSTOMER)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.name, "John Doe")

    def test_create_user_without_email_raises_error(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="SecurePassword123!")

    def test_create_superuser(self):
        admin_user = User.objects.create_superuser(
            email="admin@musclemax.com",
            password="AdminPassword123!",
        )
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertEqual(admin_user.role, User.ROLE_ADMIN)
        self.assertTrue(admin_user.is_admin_role)

    def test_name_property_fallback(self):
        user = User.objects.create_user(email="noname@musclemax.com", password="Password123!")
        self.assertEqual(user.name, "noname")


class AuthAPITests(APITestCase):
    def setUp(self):
        self.register_url = reverse("register")
        self.login_url = reverse("login")
        self.token_refresh_url = reverse("token_refresh")
        self.profile_url = reverse("profile")
        self.change_password_url = reverse("change_password")
        self.user_list_url = reverse("user_list")

        self.user_data = {
            "email": "customer@musclemax.com",
            "password": "CustomerPass123!",
            "name": "Alex Johnson",
            "phone": "+1234567890",
        }
        self.user = User.objects.create_user(
            email=self.user_data["email"],
            password=self.user_data["password"],
            first_name="Alex",
            last_name="Johnson",
            phone=self.user_data["phone"],
        )

        self.admin_user = User.objects.create_superuser(
            email="super@musclemax.com",
            password="SuperPass123!",
            first_name="Super",
            last_name="Admin",
            role=User.ROLE_ADMIN,
        )

    def test_registration_success(self):
        data = {
            "email": "newuser@musclemax.com",
            "password": "NewUserStrongPass123!",
            "name": "Jane Doe",
            "phone": "+9876543210",
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["email"], data["email"])
        self.assertEqual(response.data["role"], User.ROLE_CUSTOMER)

        created_user = User.objects.get(email=data["email"])
        self.assertEqual(created_user.role, User.ROLE_CUSTOMER)
        self.assertFalse(created_user.is_staff)

    def test_registration_duplicate_email_fails(self):
        data = {
            "email": "customer@musclemax.com",
            "password": "AnotherPassword123!",
            "name": "Duplicate User",
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_registration_cannot_self_promote_to_admin(self):
        data = {
            "email": "hacker@musclemax.com",
            "password": "HackerPass123!",
            "role": "admin",
            "is_staff": True,
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="hacker@musclemax.com")
        self.assertEqual(user.role, User.ROLE_CUSTOMER)
        self.assertFalse(user.is_staff)

    def test_login_success(self):
        data = {
            "email": self.user_data["email"],
            "password": self.user_data["password"],
        }
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], self.user_data["email"])

    def test_login_invalid_credentials(self):
        data = {
            "email": self.user_data["email"],
            "password": "WrongPassword!",
        }
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_token_refresh(self):
        refresh = RefreshToken.for_user(self.user)
        response = self.client.post(self.token_refresh_url, {"refresh": str(refresh)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_get_profile_authenticated(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["phone"], self.user.phone)

    def test_get_profile_unauthenticated(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_profile(self):
        self.client.force_authenticate(user=self.user)
        update_data = {
            "first_name": "Alexander",
            "phone": "+1112223333",
        }
        response = self.client.patch(self.profile_url, update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Alexander")
        self.assertEqual(self.user.phone, "+1112223333")

    def test_update_profile_cannot_change_role(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(self.profile_url, {"role": "admin"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.ROLE_CUSTOMER)

    def test_change_password_success(self):
        self.client.force_authenticate(user=self.user)
        data = {
            "old_password": self.user_data["password"],
            "new_password": "BrandNewPassword123!",
        }
        response = self.client.post(self.change_password_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNewPassword123!"))

    def test_change_password_wrong_old_password(self):
        self.client.force_authenticate(user=self.user)
        data = {
            "old_password": "IncorrectPassword123!",
            "new_password": "BrandNewPassword123!",
        }
        response = self.client.post(self.change_password_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_user_list_permission(self):
        # Customer cannot view user list
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.user_list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Admin can view user list
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.user_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("results", response.data)), 2)

