from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenBlacklistView
from .serializers import LoginSerializer, RefreshSerializer, LogoutSerializer, UserMeSerializer
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from rest_framework import status

class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response.data["access_token"] = response.data.pop("access")
        response.data["refresh_token"] = response.data.pop("refresh")
        return response

class RefreshView(TokenRefreshView):
    serializer_class = RefreshSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response.data["access_token"] = response.data.pop("access")
        response.data["refresh_token"] = response.data.pop("refresh")
        return response
    
class LogoutView(TokenBlacklistView):
    serializer_class = LogoutSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    serializer = UserMeSerializer(request.user)
    return Response(serializer.data)
    
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_all(request):
    tokens = OutstandingToken.objects.filter(user=request.user)
    for token in tokens:
        BlacklistedToken.objects.get_or_create(token=token)
    return Response(status=status.HTTP_200_OK)