from django.urls import path
from . import views

app_name = "ielts"

urlpatterns = [
    path('', views.home, name='home'),
    path("reading/", views.reading_home, name="reading"),

]