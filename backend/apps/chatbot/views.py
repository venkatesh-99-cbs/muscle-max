import logging
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.chatbot.serializers import ChatAskSerializer
from apps.chatbot.services import generate_mock_answer

logger = logging.getLogger(__name__)


class ChatAskView(APIView):
    """
    API endpoint for customer chatbot inquiries.
    - POST /api/chatbot/ask/ : Guest accessible prompt processing.

    # TODO:
    # Future RAG integration by team lead:
    # Replace generate_mock_answer with actual retriever + generator pipeline.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "chatbot_anon"

    def post(self, request, *args, **kwargs):
        serializer = ChatAskSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        question = serializer.validated_data["question"]

        try:
            # Call service layer (currently temporary mock service)
            response_data = generate_mock_answer(question)
            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as exc:
            logger.error("Unexpected error in ChatAskView: %s", exc, exc_info=True)
            return Response(
                {
                    "detail": "An unexpected error occurred while processing your request. Please try again later."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
