from django.urls import path
from . import views

app_name = 'swaps'

urlpatterns = [
    path('create/', views.create_swap_view, name='create'),
    path('my-requests/', views.my_swaps_list_view, name='list'),
    path('cancel/<int:swap_id>/', views.cancel_swap_view, name='cancel'),
    path('matches/', views.swap_matches_view, name='matches'),
    path('execute/<int:swap_id>/', views.execute_swap_view, name='execute'),
]
