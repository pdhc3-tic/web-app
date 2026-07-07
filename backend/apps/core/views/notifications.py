from django.core.cache import cache
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models.notifications import Notification, _invalidate_unread_cache
from apps.core.serializers import NotificationSerializer
from apps.core.throttling import NotificationUnreadCountThrottle


class NotificationPagination(LimitOffsetPagination):
    default_limit = 20


class NotificationListView(generics.ListAPIView):
    """GET /api/v1/notifications/me/ — notificações do usuário autenticado."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination
    ordering = ["-enviado_em"]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by("-enviado_em")


class NotificationMarkReadView(generics.UpdateAPIView):
    """PATCH /api/v1/notifications/{id}/read/ — marca como lida."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["patch"]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def partial_update(self, request, *args, **kwargs):
        notification = self.get_object()

        if notification.lido_em is None:
            notification.lido_em = timezone.now()
            notification.save(update_fields=["lido_em"])
            _invalidate_unread_cache(request.user.pk)

        serializer = self.get_serializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    """POST /api/v1/notifications/mark-all-read/ — marca todas como lidas."""
    updated_count = Notification.objects.filter(
        user=request.user,
        lido_em__isnull=True,
    ).update(lido_em=timezone.now())

    if updated_count > 0:
        _invalidate_unread_cache(request.user.pk)

    return Response({"updated_count": updated_count}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([NotificationUnreadCountThrottle])
def unread_count(request):
    """GET /api/v1/notifications/me/unread-count/ — contagem de não-lidas com cache 30s."""
    cache_key = f"notification_unread_count_{request.user.pk}"
    count = cache.get(cache_key)

    if count is None:
        count = Notification.objects.filter(
            user=request.user,
            lido_em__isnull=True,
        ).count()
        cache.set(cache_key, count, timeout=30)

    return Response({"count": count}, status=status.HTTP_200_OK)
