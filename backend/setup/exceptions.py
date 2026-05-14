import math
from rest_framework.views import exception_handler
from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if isinstance(exc, Throttled):
        retry_after = math.ceil(exc.wait) if exc.wait else 60
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
