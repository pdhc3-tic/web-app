import math
import logging

from rest_framework.views import exception_handler
from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from rest_framework import status


security_logger = logging.getLogger("security")


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if isinstance(exc, Throttled):
        retry_after = math.ceil(exc.wait) if exc.wait else 60
        request = context.get("request")
        user = getattr(request, "user", None) if request is not None else None
        security_logger.warning(
            "request.throttled user_id=%s ip=%s method=%s path=%s retry_after=%s",
            getattr(user, "pk", None),
            request.META.get("REMOTE_ADDR") if request is not None else None,
            request.method if request is not None else None,
            request.path if request is not None else None,
            retry_after,
        )
        response = Response(
            {
                "code": "THROTTLED",
                "message": f"Muitas tentativas. Tente novamente em {retry_after} segundos.",
                "retry_after": retry_after,
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        response["Retry-After"] = retry_after

    return response
