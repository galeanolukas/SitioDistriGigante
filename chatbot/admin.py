from django.contrib import admin
from .models import AssistantConfig, AssistantKnowledge, AssistantConversation, AssistantMessage

@admin.register(AssistantConfig)
class AssistantConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'ai_model', 'is_active', 'created_at']
    list_filter = ['is_active', 'role', 'ai_model']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(AssistantKnowledge)
class AssistantKnowledgeAdmin(admin.ModelAdmin):
    list_display = ['title', 'knowledge_type', 'priority', 'is_active']
    list_filter = ['knowledge_type', 'is_active', 'priority']
    search_fields = ['title', 'content', 'tags']
    list_editable = ['priority', 'is_active']

@admin.register(AssistantConversation)
class AssistantConversationAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'user', 'started_at', 'message_count']
    list_filter = ['started_at']
    readonly_fields = ['session_id', 'started_at', 'ended_at']

@admin.register(AssistantMessage)
class AssistantMessageAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'message_type', 'timestamp', 'response_time']
    list_filter = ['message_type', 'timestamp']
    readonly_fields = ['timestamp']
