from django.urls import path

from inspection import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.list_view, name="list"),
    path("inspections/new/", views.create_view, name="create"),
    path("inspections/<int:pk>/", views.detail_view, name="detail"),
    path("inspections/<int:pk>/note/", views.note_edit_view, name="note_edit"),
    path("search/", views.search_view, name="search"),
    path("archives/", views.archive_list_view, name="archive_list"),
    path("archives/new/", views.archive_save_view, name="archive_save"),
    path("archives/<int:pk>/", views.archive_detail_view, name="archive_detail"),
]
