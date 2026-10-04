from django.contrib import admin
from .models import Job, Review, Post

class AuditAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Job)
class JobAdmin(AuditAdmin):
    list_display = ['title', 'owner', 'city', 'auto_publish', 'created_at']

@admin.register(Review)
class ReviewAdmin(AuditAdmin):
    list_display = ['job', 'stage', 'public_consent', 'consent_at']
    exclude = ['token_hash', 'chat_id']

@admin.register(Post)
class PostAdmin(AuditAdmin):
    list_display = ['job', 'status', 'published_at']
    exclude = ['media_token']
