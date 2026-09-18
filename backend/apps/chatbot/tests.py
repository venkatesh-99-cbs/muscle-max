from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class ChatbotAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        self.ask_url = reverse("chatbot-ask")

    def test_1_valid_guest_request(self):
        """1. Valid guest request returns 200 OK without authentication."""
        payload = {"question": "What is creatine?"}
        response = self.client.post(self.ask_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("answer", response.data)
        self.assertIn("sources", response.data)
        self.assertIn("grounded", response.data)
        self.assertEqual(response.data["answer"], "The AI chatbot integration is currently being prepared.")
        self.assertEqual(response.data["sources"], [])
        self.assertIs(response.data["grounded"], False)

    def test_2_missing_question(self):
        """2. Missing question field returns 400 Bad Request."""
        payload = {}
        response = self.client.post(self.ask_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("question", response.data)

    def test_3_empty_question(self):
        """3. Empty question returns 400 Bad Request."""
        payload = {"question": ""}
        response = self.client.post(self.ask_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("question", response.data)

    def test_4_whitespace_only_question(self):
        """4. Whitespace-only question returns 400 Bad Request."""
        payload = {"question": "   \n\t  "}
        response = self.client.post(self.ask_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("question", response.data)

    def test_5_non_string_question(self):
        """5. Non-string question returns 400 Bad Request."""
        payload = {"question": 12345}
        response = self.client.post(self.ask_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("question", response.data)

    def test_6_question_exceeding_max_length(self):
        """6. Question exceeding 1000 characters returns 400 Bad Request."""
        long_question = "A" * 1001
        payload = {"question": long_question}
        response = self.client.post(self.ask_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("question", response.data)

    def test_7_response_structure(self):
        """7. Response structure strictly contains answer, sources, and grounded."""
        payload = {"question": "Do you offer whey protein isolate?"}
        response = self.client.post(self.ask_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data.keys()), {"answer", "sources", "grounded"})
        self.assertIsInstance(response.data["answer"], str)
        self.assertIsInstance(response.data["sources"], list)
        self.assertIsInstance(response.data["grounded"], bool)

    def test_8_http_method_validation(self):
        """8. HTTP GET/PUT/DELETE requests to /api/chatbot/ask/ return 405 Method Not Allowed."""
        res_get = self.client.get(self.ask_url)
        self.assertEqual(res_get.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        res_put = self.client.put(self.ask_url, {"question": "Test"})
        self.assertEqual(res_put.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        res_delete = self.client.delete(self.ask_url)
        self.assertEqual(res_delete.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_9_unexpected_server_error_handled_gracefully(self):
        """Unexpected internal exceptions return 500 without leaking stack trace details."""
        with patch("apps.chatbot.views.generate_mock_answer", side_effect=RuntimeError("Unexpected error")):
            payload = {"question": "How much is whey?"}
            response = self.client.post(self.ask_url, payload, format="json")

            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.assertIn("detail", response.data)
            self.assertNotIn("Unexpected error", str(response.data))

    def test_10_rate_limiting_throttling(self):
        """Public chatbot endpoint enforces rate limiting (chatbot_anon throttle scope)."""
        payload = {"question": "Rate limit check"}
        responses = [self.client.post(self.ask_url, payload, format="json") for _ in range(12)]
        statuses = [r.status_code for r in responses]
        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, statuses)


