from rest_framework.views import exception_handler
from rest_framework.response import Response
from .integrations import IntegrationError

def handler(exc, context):
    if isinstance(exc, IntegrationError):
        return Response({'detail': str(exc)}, status=503)
    return exception_handler(exc, context)
