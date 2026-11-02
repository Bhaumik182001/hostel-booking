from django.urls import path, re_path
from . import views

app_name = 'rooms'

urlpatterns = [
    # Path converters (Unit II)
    path('', views.room_list_view, name='room_list'),
    path('<int:room_id>/', views.room_detail_view, name='room_detail'),

    # Regular expression URL routing (Unit II)
    re_path(
        r'^block/(?P<block_code>[A-Za-z0-9-]+)/(?P<room_num>\d+)/$',
        views.room_regex_search_view,
        name='regex_search',
    ),
]
