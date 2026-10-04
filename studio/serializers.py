import io
import uuid
from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.files.base import ContentFile
from rest_framework import serializers
from .models import Job, Review, Post

class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['id', 'stage', 'ai_consent', 'public_consent', 'approved_text', 'consent_at', 'expires_at']

class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ['id', 'status', 'caption', 'error', 'permalink', 'media_id', 'due_at', 'published_at']

class JobSerializer(serializers.ModelSerializer):
    photo = serializers.FileField(write_only=True, required=False)
    photo_present = serializers.SerializerMethodField()
    review = ReviewSerializer(read_only=True)
    post = PostSerializer(read_only=True)
    class Meta:
        model = Job
        fields = ['id', 'title', 'description', 'city', 'photo', 'photo_present', 'photo_rights',
            'auto_publish', 'is_demo', 'created_at', 'review', 'post']
        read_only_fields = ['id', 'is_demo', 'created_at']
    def get_photo_present(self, obj) -> bool:
        return bool(obj.photo)
    def validate_photo(self, value):
        if value.size > 8 * 1024 * 1024:
            raise serializers.ValidationError('Размер фотографии: максимум 8 МБ.')
        try:
            with Image.open(value) as source:
                if source.format not in ('JPEG', 'PNG', 'WEBP'):
                    raise ValueError()
                if source.width * source.height > 24_000_000 or min(source.size) < 320:
                    raise ValueError()
                image = ImageOps.exif_transpose(source).convert('RGB')
                image.thumbnail((1080, 1350))
                width, height = image.size
                if width / height < .8:
                    width = round(height * .8)
                elif width / height > 1.91:
                    height = round(width / 1.91)
                canvas = Image.new('RGB', (width, height), 'white')
                canvas.paste(image, ((width-image.width)//2, (height-image.height)//2))
                buffer = io.BytesIO()
                canvas.save(buffer, 'JPEG', quality=90)
            return ContentFile(buffer.getvalue(), name=f'{uuid.uuid4()}.jpg')
        except (UnidentifiedImageError, ValueError, OSError, Image.DecompressionBombError):
            raise serializers.ValidationError('Нужна фотография JPEG, PNG или WebP: от 320 px, до 24 мегапикселей.') from None
    def validate(self, attrs):
        if attrs.get('auto_publish') and (not attrs.get('photo_rights') or not attrs.get('photo')):
            raise serializers.ValidationError('Для автопубликации загрузите фото и подтвердите право использовать его.')
        return attrs

class MessageSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=350, required=False, allow_blank=True)
    action = serializers.ChoiceField(choices=['ai_yes', 'approve', 'edit', 'public_yes', 'public_no', 'stop'], required=False)

class ScheduleSerializer(serializers.Serializer):
    due_at = serializers.DateTimeField(required=False)
