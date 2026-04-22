from django.urls import path
from . import views

app_name = "topik"

urlpatterns = [
    path("", views.topik_home, name="topik_home"),

    # TOPIK EXAM LISTS
    path("mock/", views.topik_mock_list, name="topik_mock_list"),
    path("reading/", views.topik_reading_list, name="topik_reading_list"),
    path("listening/", views.topik_listening_list, name="topik_listening_list"),
    path("writing/", views.topik_writing_list, name="topik_writing_list"),
    path("progress/", views.topik_progress, name="topik_progress"),

    # TOPIK EXAM DETAIL / START
    path("exam/<slug:slug>/", views.topik_exam_detail, name="topik_exam_detail"),
    path("exam/<slug:slug>/start/", views.start_topik_exam, name="start_topik_exam"),
    path("exam/<slug:slug>/start-reading/", views.start_topik_reading_exam, name="start_topik_reading_exam"),
    path("exam/<slug:slug>/start-listening/", views.start_topik_listening_exam, name="start_topik_listening_exam"),
    path("exam/<slug:slug>/start-writing/", views.start_topik_writing_exam, name="start_topik_writing_exam"),

    # TOPIK EXAM ATTEMPT FLOW
    path("exam/attempt/<int:attempt_id>/solve/", views.topik_exam_solve, name="topik_exam_solve"),
    path(
        "exam/attempt/<int:attempt_id>/solve/<str:section_name>/",
        views.topik_exam_solve_section,
        name="topik_exam_solve_section",
    ),
    path("exam/attempt/<int:attempt_id>/advance/", views.advance_topik_exam_section, name="advance_topik_exam_section"),
    path("exam/attempt/<int:attempt_id>/autosave/", views.autosave_answer, name="autosave_answer"),
    path(
        "exam/attempt/<int:attempt_id>/writing/autosave/",
        views.autosave_writing_submission,
        name="autosave_writing_submission",
    ),
    path("exam/attempt/<int:attempt_id>/log-event/", views.log_exam_event, name="log_exam_event"),
    path("exam/attempt/<int:attempt_id>/submit/", views.submit_topik_exam, name="submit_topik_exam"),
    path("exam/attempt/<int:attempt_id>/finish/", views.finish_topik_exam, name="finish_topik_exam"),
    path("exam/attempt/<int:attempt_id>/result/", views.topik_exam_result, name="topik_exam_result"),
    path("exam/attempt/<int:attempt_id>/ai-evaluate/", views.evaluate_topik_exam_ai, name="evaluate_topik_exam_ai"),

    # SPEAKING TEST LIST / START
    path("speaking/", views.speaking_test_list, name="speaking_test_list"),
    path("speaking/start/<int:test_id>/", views.start_speaking_test, name="start_speaking_test"),

    # SPEAKING ATTEMPT FLOW
    path("speaking/attempt/<int:attempt_id>/", views.speaking_test_room, name="speaking_test_room"),
    path(
        "speaking/attempt/<int:attempt_id>/answer/<int:question_id>/",
        views.save_speaking_answer,
        name="save_speaking_answer",
    ),
    path(
        "speaking/attempt/<int:attempt_id>/submit/",
        views.submit_speaking_test,
        name="submit_speaking_test",
    ),
    path(
        "speaking/attempt/<int:attempt_id>/result/",
        views.speaking_result,
        name="speaking_result",
    ),

]