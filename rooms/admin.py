from django.contrib import admin
from .models import HostelBlock, Room


@admin.register(HostelBlock)
class HostelBlockAdmin(admin.ModelAdmin):
    list_display = ('name', 'gender_restriction')
    list_filter = ('gender_restriction',)
    search_fields = ('name',)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'block', 'capacity')
    list_filter = ('block', 'capacity')
    search_fields = ('room_number', 'block__name')
