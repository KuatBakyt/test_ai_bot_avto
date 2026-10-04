from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse, OpenApiParameter
from .models import Job, Review, Post
from .serializers import JobSerializer, MessageSerializer, ScheduleSerializer
from .reviews import issue_invitation, interact
from .tasks import permitted, advance

@extend_schema(responses=OpenApiResponse(description='Integration configuration without secrets'))
@api_view(['GET'])
def configuration(request):
    return Response({'demo_mode': settings.DEMO_MODE, 'instagram_enabled': settings.INSTAGRAM_PUBLISH_ENABLED,
        'telegram_configured': bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_BOT_USERNAME),
        'ai_configured': bool(settings.OPENAI_API_KEY), 'model': settings.OPENAI_MODEL})

def health(request):
    return JsonResponse({'status': 'ok'})

@extend_schema_view(
    retrieve=extend_schema(parameters=[OpenApiParameter('id', str, location='path')]))
class JobViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = JobSerializer
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Job.objects.none()
        return Job.objects.filter(owner=self.request.user).select_related('review', 'post').order_by('-created_at')
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
    @extend_schema(responses={(200, 'image/jpeg'): bytes})
    @action(detail=True, methods=['get'])
    def photo(self, request, pk=None):
        job = self.get_object()
        if not job.photo:
            raise Http404()
        result = FileResponse(job.photo.open('rb'), content_type='image/jpeg')
        result['Cache-Control'] = 'private, no-store'
        return result
    @extend_schema(request=None, responses=OpenApiResponse(description='Action result'))
    @action(detail=True, methods=['post'])
    def invite(self, request, pk=None):
        job = self.get_object()
        if not settings.DEMO_MODE and not (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_BOT_USERNAME):
            raise ValidationError('Сначала настройте Telegram токен и username.')
        review, token = issue_invitation(job)
        link = f'https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={token}' if settings.TELEGRAM_BOT_USERNAME else ''
        # Token is returned only on issuance. Database stores only its hash.
        return Response({'review_id': str(review.id), 'telegram_link': link, 'expires_at': review.expires_at}, status=201)
    @extend_schema(request=MessageSerializer, responses=OpenApiResponse(description='Action result'))
    @action(detail=True, methods=['post'], url_path='demo-chat')
    def demo_chat(self, request, pk=None):
        if not settings.DEMO_MODE:
            raise ValidationError('Симулятор доступен только в DEMO_MODE.')
        job = self.get_object()
        if not job.is_demo:
            raise ValidationError('Настоящий отзыв нельзя заполнить через симулятор.')
        if not hasattr(job, 'review'):
            raise ValidationError('Сначала создайте приглашение.')
        serializer = MessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            Job.objects.select_for_update().get(pk=job.pk)
            review = Review.objects.select_for_update().get(job=job)
            if review.chat_id is not None and review.chat_id != -request.user.pk:
                raise ValidationError('Этот отзыв уже открыт в Telegram.')
            if review.stage == 'INVITED':
                review.chat_id, review.stage = -request.user.pk, 'CONSENT'
                review.save()
            result = interact(review.pk, -request.user.pk, **serializer.validated_data)
        return Response(result)
    @extend_schema(request=None, responses=OpenApiResponse(description='Action result'))
    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        job = self.get_object()
        with transaction.atomic():
            job = Job.objects.select_for_update().get(pk=job.pk)
            if not permitted(job):
                raise ValidationError('Нужны подтверждённый отзыв, согласия клиента и разрешённое фото.')
            post, created = Post.objects.get_or_create(job=job)
            if not created and post.status != 'GENERATING':
                raise ValidationError('Пост уже подготовлен. Используйте действия в карточке поста.')
        if settings.CELERY_TASK_ALWAYS_EAGER:
            advance.delay(str(post.pk))
        return Response({'status': 'GENERATING'}, status=202)
    @extend_schema(request=ScheduleSerializer, responses=OpenApiResponse(description='Action result'))
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        job = self.get_object()
        serializer = ScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        due = serializer.validated_data.get('due_at', timezone.now())
        if due > timezone.now() + timedelta(days=30):
            raise ValidationError('Запланировать можно максимум на 30 дней.')
        with transaction.atomic():
            job = Job.objects.select_for_update().get(pk=job.pk)
            post = Post.objects.select_for_update().filter(job=job).first()
            if not permitted(job) or not post or post.status != 'DRAFT':
                raise ValidationError('Публикация возможна только из готового черновика с разрешениями.')
            if not settings.DEMO_MODE and not settings.INSTAGRAM_PUBLISH_ENABLED:
                raise ValidationError('Реальная публикация отключена в .env.')
            post.status, post.due_at, post.error = 'QUEUED', max(due, timezone.now()), ''
            post.save()
        if settings.CELERY_TASK_ALWAYS_EAGER:
            advance.delay(str(post.pk))
        return Response({'status': 'QUEUED'}, status=202)
    @extend_schema(request=None, responses=OpenApiResponse(description='Action result'))
    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        job = self.get_object()
        with transaction.atomic():
            job = Job.objects.select_for_update().get(pk=job.pk)
            post = Post.objects.select_for_update().filter(job=job).first()
            if not post or post.status != 'FAILED' or not permitted(job):
                raise ValidationError('Повтор доступен только после явной ошибки. Неизвестный исход нельзя повторять.')
            post.status = 'QUEUED' if post.caption else 'GENERATING'
            post.container_id, post.error, post.due_at = '', '', timezone.now()
            post.save()
        return Response({'status': post.status}, status=202)

# Public only during container processing, with an unguessable per-post capability URL.
# No public directory, no original photo URLs, no user-supplied file paths.
def public_photo(request, token):
    post = Post.objects.select_related('job__review').filter(media_token=token,
        status__in=['QUEUED', 'CREATING', 'WAITING', 'PUBLISHING']).first()
    if settings.DEMO_MODE or not settings.INSTAGRAM_PUBLISH_ENABLED or not post or post.job.is_demo or not permitted(post.job):
        raise Http404()
    result = FileResponse(post.job.photo.open('rb'), content_type='image/jpeg')
    result['Cache-Control'] = 'no-store'
    result['X-Robots-Tag'] = 'noindex'
    return result
