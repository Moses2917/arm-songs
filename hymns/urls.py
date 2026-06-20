from django.urls import path

from . import views

app_name = "hymns"

urlpatterns = [
    path("", views.home, name="home"),
    path("tsank/", views.tsank_number, name="tsank_number"),
    path("themes/", views.themes_list, name="themes_list"),
    path("themes/<int:number>/", views.theme_detail, name="theme_detail"),
    path("az/", views.alpha_index, name="alpha_index"),
    path("az/<str:letter>/", views.alpha_letter, name="alpha_letter"),
    path("search/", views.search, name="search"),
    path("song/<str:book>/<str:number>/", views.song_detail, name="song_detail"),
]
