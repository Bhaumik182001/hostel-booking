from django.contrib import admin
from .models import StudentProfile


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_room')
    list_filter = ('current_room__block',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email', 'current_room__room_number')
