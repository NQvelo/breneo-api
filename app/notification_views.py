from django.conf import settings
from django.db.models import Q
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import JobNotification, Notification
from .serializers import (
    InternalNotificationCreateSerializer,
    JobNotificationCreateSerializer,
    NotificationCreateSerializer,
    NotificationSerializer,
)


def _me_notifications_queryset(user):
    return Notification.objects.filter(
        Q(recipient=user) | Q(recipient__isnull=True)
    )


def _check_internal_notifications_key(request):
    expected = getattr(settings, "NOTIFICATIONS_INTERNAL_KEY", "") or ""
    provided = request.headers.get("X-Internal-Key") or request.META.get(
        "HTTP_X_INTERNAL_KEY", ""
    )
    return bool(expected) and provided == expected


class MeNotificationListCreateView(APIView):
    """GET/POST /api/me/notifications/ — list (personal + broadcast) or create for self."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = _me_notifications_queryset(request.user)
        kind = request.query_params.get("kind", "").strip()
        if kind:
            qs = qs.filter(kind=kind)
        data = NotificationSerializer(qs, many=True).data
        return Response({"results": data})

    def post(self, request):
        serializer = NotificationCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        notification = serializer.save()
        return Response(
            NotificationSerializer(notification).data,
            status=status.HTTP_201_CREATED,
        )


class MeNotificationMarkReadView(APIView):
    """PATCH /api/me/notifications/<pk>/read/ — mark owned notification as read."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk)
        except Notification.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if notification.recipient_id is None or notification.recipient_id != request.user.id:
            return Response(
                {"detail": "You may only mark your own notifications as read."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read", "updated_at"])
        return Response(NotificationSerializer(notification).data)


class MeNotificationReadAllView(APIView):
    """PATCH /api/me/notifications/read-all/ — mark all personal unread as read."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True)
        return Response({"updated": updated})


class MeJobNotificationView(APIView):
    """GET/POST /api/me/job-notifications/ — dedup job match notifications."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        job_ids = list(
            JobNotification.objects.filter(user=request.user)
            .order_by("-notified_at")
            .values_list("job_id", flat=True)
        )
        return Response({"job_ids": job_ids})

    def post(self, request):
        serializer = JobNotificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job_id = serializer.validated_data["job_id"]
        _, created = JobNotification.objects.get_or_create(
            user=request.user, job_id=job_id
        )
        return Response(
            {"job_id": job_id},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class InternalNotificationCreateView(APIView):
    """POST /api/internal/notifications/ — BFF only (X-Internal-Key)."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        if not _check_internal_notifications_key(request):
            return Response(
                {"detail": "Invalid or missing internal key."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        serializer = InternalNotificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notification = serializer.save()
        return Response(
            NotificationSerializer(notification).data,
            status=status.HTTP_201_CREATED,
        )
