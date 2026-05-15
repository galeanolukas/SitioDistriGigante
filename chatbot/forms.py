# forms.py
from django import forms
from .models import AssistantConfig, AssistantKnowledge

class AssistantConfigForm(forms.ModelForm):
    class Meta:
        model = AssistantConfig
        fields = [
            'name', 'role', 'ai_model', 'custom_model_name',
            'system_prompt', 'temperature', 'max_tokens',
            'is_active', 'knowledge_base_enabled',
            'product_catalog_access', 'order_access'
        ]
        widgets = {
            'temperature': forms.NumberInput(attrs={
                'type': 'range',
                'min': '0.0',
                'max': '1.0',
                'step': '0.1'
            }),
            'system_prompt': forms.Textarea(attrs={
                'rows': 8,
                'class': 'w3-input w3-border',
                'placeholder': 'Escribe las instrucciones base para el asistente...'
            }),
        }

class AssistantKnowledgeForm(forms.ModelForm):
    class Meta:
        model = AssistantKnowledge
        fields = ['title', 'content', 'knowledge_type', 'priority', 'tags', 'is_active']
        widgets = {
            'tags': forms.TextInput(attrs={
                'placeholder': 'productos, envíos, garantía, precios...'
            })
        }
