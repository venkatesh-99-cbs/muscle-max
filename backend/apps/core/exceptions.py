import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("musclemax")


def custom_exception_handler(exc, context):
    """
    Centralized exception handler that preserves DRF validation error formatting
    ({field: ["error message"]}) as defined in docs/API_WORKFLOW.md, while catching
    unhandled server errors and logging them cleanly.
    """
    response = exception_handler(exc, context)

    if response is not None:
        return response

    view = context.get("view")
    view_name = view.__class__.__name__ if view else "Unknown"
    logger.exception("Unhandled exception in view %s: %s", view_name, str(exc))

    return Response(
        {"detail": "An unexpected server error occurred. Please try again later."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )

