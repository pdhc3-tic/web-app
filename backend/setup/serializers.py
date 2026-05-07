from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer

from rest_framework import serializers

class LoginSerializer(TokenObtainPairSerializer):
    senha = serializers.CharField(write_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("password")
         
    def validate(self, attrs):
        attrs["password"] = attrs.pop("senha")
        return super().validate(attrs)
    
class RefreshSerializer(TokenRefreshSerializer):
    refresh_token = serializers.CharField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("refresh")

    def validate(self, attrs):
        attrs["refresh"] = attrs.pop("refresh_token")
        return super().validate(attrs)