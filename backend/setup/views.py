from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user
    return Response(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "permissions": sorted(user.get_all_permissions()),
        }
    )

class LoginSerializer(TokenObtainPairSerializer):
    senha = serializers.CharField(write_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("password")
         
    def validate(self, attrs):
        attrs["password"] = attrs.pop("senha")
        return super().validate(attrs)
    
class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response.data["access_token"] = response.data.pop("access")
        response.data["refresh_token"] = response.data.pop("refresh")
        return response