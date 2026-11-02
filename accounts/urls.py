from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.user_login_view, name='login'),
    path('logout/', views.user_logout_view, name='logout'),
    path('dashboard/', views.student_dashboard_view, name='dashboard'),
    path('set-preference/', views.set_preference_cookie_view, name='set_preference'),
]
