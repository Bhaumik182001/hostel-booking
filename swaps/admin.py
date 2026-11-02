from django.contrib import admin
from .models import SwapRequest


@admin.register(SwapRequest)
class SwapRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'requester', 'target_room', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at', 'target_room__block')
    search_fields = ('requester__user__username', 'target_room__room_number', 'target_room__block__name')
