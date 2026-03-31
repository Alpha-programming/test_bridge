from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = "ielts"

urlpatterns = [

    # 🏠 MAIN
    path('', views.home, name='home'),
    path("profile/", views.profile_view, name="profile"),
    path("profile/edit", views.edit_profile, name="profile_edit"),
    path("password-change/", auth_views.PasswordChangeView.as_view(template_name="ielts/profile/password_change.html"), name="password_change"),
    path("pricing/", views.pricing_view, name="pricing"),
    path("upgrade/<str:plan>/", views.upgrade_plan, name="upgrade_plan"),

    # =========================
    # 📘 READING
    # =========================
    path("reading/", views.reading_home, name="reading"),

    path("reading/start/<int:test_id>/", views.start_test, name="reading_start"),
    path("reading/solve/<int:user_test_id>/", views.solve_test, name="reading_solve"),
    path("reading/save-answer/", views.save_answer, name="reading_save_answer"),
    path("reading/submit/<int:user_test_id>/", views.submit_test, name="reading_submit"),
    path("reading/result/<int:user_test_id>/", views.result_view, name="reading_result"),
    path("reading/overall-ai/", views.reading_overall_ai, name="reading_overall_ai"),

    # =========================
    # 🎧 LISTENING
    # =========================
    path("listening/", views.listening_home, name="listening"),

    path("listening/start/<int:test_id>/", views.start_listening, name="listening_start"),
    path("listening/solve/<int:user_test_id>/", views.solve_listening, name="listening_solve"),
    path("listening/save-answer/", views.save_listening_answer, name="listening_save_answer"),
    path("listening/submit/<int:user_test_id>/", views.submit_listening, name="listening_submit"),
    path("listening/result/<int:user_test_id>/", views.listening_result, name="listening_result"),
    path("listening/ai/", views.listening_overall_ai, name="listening_overall_ai"),

    # =========================
    # 🎤 Writing
    # =========================
    path("writing/", views.writing_home, name="writing"),
    path("writing/start/<int:test_id>/", views.start_writing, name="writing_start"),
    path("writing/solve/<int:user_test_id>/", views.writing_solve, name="writing_solve"),
    path("writing/save/", views.save_writing_answer, name="save_writing_answer"),
    path("writing/submit/<int:user_test_id>/", views.submit_writing, name="writing_submit"),
    path("writing/result/<int:result_id>/", views.writing_result, name="writing_result"),

    # =========================
    # 🎤 SPEAKING
    # =========================
    path("speaking/", views.speaking_home, name="speaking"),
    path("speaking/start/<int:test_id>/", views.start_speaking, name="speaking_start"),
    path("speaking/solve/<int:user_test_id>/", views.solve_speaking, name="speaking_solve"),
    path("speaking/upload/", views.upload_speaking_answer, name="speaking_upload"),
    path("speaking/submit/<int:user_test_id>/", views.submit_speaking, name="speaking_submit"),
    path("speaking/result/<int:user_test_id>/", views.speaking_result, name="speaking_result"),
]