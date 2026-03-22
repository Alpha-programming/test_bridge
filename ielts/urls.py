from django.urls import path
from . import views

app_name = "ielts"

urlpatterns = [
    path('', views.home, name='home'),
    path("reading/", views.reading_home, name="reading"),
    path("start/<int:test_id>/", views.start_test, name="start_test"),
    path("solve/<int:user_test_id>/", views.solve_test, name="solve_test"),
    path("save-answer/", views.save_answer, name="save_answer"),
    path("submit/<int:user_test_id>/", views.submit_test, name="submit_test"),
    path("result/<int:user_test_id>/", views.result_view, name="result"),
]