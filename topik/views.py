from collections import defaultdict
from django.db.models import Avg, Max, Count
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods
from django.urls import reverse
from .models import *
from topik.services.progress_advice import update_progress_advice_for_user

from .services.speaking_ai import evaluate_speaking_answer, evaluate_full_speaking_attempt,transcribe_speaking_audio
from .services.writing_scoring import score_writing_submission
from .utills import *


def topik_home(request):
    user = request.user

    featured_exams = list(
        TopikExam.objects.filter(is_active=True)
        .prefetch_related("sections")
        .order_by("-exam_number", "-created_at")[:3]
    )

    for exam in featured_exams:
        active_sections = exam.sections.filter(is_active=True).order_by("order")
        section_names = [section.get_name_display() for section in active_sections]
        exam.section_names = section_names
        exam.sections_display = " + ".join(section_names) if section_names else "No sections"
        exam.questions_count = sum(section.total_questions or 0 for section in active_sections)

    stats = {
        "total_attempts": 0,
        "best_score": 0,
        "average_score": 0,
        "progress_percent": 0,
        "current_goal": "Start your first TOPIK exam",
        "recent_activity": [],
        "skill_performance": [],
    }

    subscription = None
    remaining_tests = 0
    remaining_ai = 0

    if user.is_authenticated:
        subscription = get_or_create_subscription(user)
        limits = subscription.get_limits()
        remaining_tests = max(0, limits["tests"] - subscription.tests_used_today)
        remaining_ai = max(0, limits["ai"] - subscription.ai_used_today)

        submitted_attempts = (
            ExamAttempt.objects.filter(
                user=user,
                status__in=[ExamAttempt.Status.SUBMITTED, ExamAttempt.Status.EVALUATED],
            )
            .select_related("exam")
            .order_by("-submitted_at")
        )

        total_attempts = submitted_attempts.count()
        best_score = round(submitted_attempts.aggregate(v=Max("total_score"))["v"] or 0)
        average_score = round(submitted_attempts.aggregate(v=Avg("total_score"))["v"] or 0)

        reading_avg = round(submitted_attempts.aggregate(v=Avg("reading_score"))["v"] or 0)
        listening_avg = round(submitted_attempts.aggregate(v=Avg("listening_score"))["v"] or 0)
        writing_avg = round(submitted_attempts.aggregate(v=Avg("writing_score"))["v"] or 0)

        has_topik2 = submitted_attempts.filter(exam__level=TopikExam.Level.TOPIK_II).exists()
        scale_max = 300 if has_topik2 else 200
        progress_percent = min(100, round((average_score / scale_max) * 100)) if average_score else 0

        current_goal = "영역별 연습을 꾸준히 이어가기"
        if best_score >= 230:
            current_goal = "TOPIK II 고득점 실력을 안정적으로 유지하기"
        elif best_score >= 190:
            current_goal = "TOPIK 6급 목표로 점수 끌어올리기"
        elif best_score >= 150:
            current_goal = "TOPIK 5급 목표로 점수 끌어올리기"
        elif best_score >= 120:
            current_goal = "TOPIK 4급 목표로 점수 끌어올리기"
        elif total_attempts > 0:
            current_goal = "약한 영역을 보완하고 점수 안정성 높이기"

        recent_activity = []
        for attempt in submitted_attempts[:4]:
            exam_type = attempt.exam.get_exam_type_display() if hasattr(attempt.exam, "get_exam_type_display") else attempt.exam.exam_type
            recent_activity.append({
                "title": attempt.exam.title,
                "subtitle": f"{attempt.submitted_at.strftime('%Y-%m-%d')} • {exam_type}",
                "score_text": f"{attempt.total_score}",
            })

        skill_performance = [
            {"name": "Reading", "score": reading_avg, "description": "Comprehension and speed across reading tasks."},
            {"name": "Listening", "score": listening_avg, "description": "Accuracy in audio understanding and response."},
            {"name": "Writing", "score": writing_avg, "description": "Structure, grammar, and task completion."},
        ]

        stats.update({
            "total_attempts": total_attempts,
            "best_score": best_score,
            "average_score": average_score,
            "progress_percent": progress_percent,
            "current_goal": current_goal,
            "recent_activity": recent_activity,
            "skill_performance": skill_performance,
        })

    context = {
        "featured_exams": featured_exams,
        "stats": stats,
        "subscription": subscription,
        "remaining_tests": remaining_tests,
        "remaining_ai": remaining_ai,
    }
    return render(request, "topik/main.html", context)
def _filter_exam_list(queryset, request):
    search = request.GET.get("search", "").strip()
    level = request.GET.get("level", "").strip()
    status = request.GET.get("status", "").strip()
    sort = request.GET.get("sort", "newest").strip()

    if search:
        queryset = queryset.filter(
            Q(title__icontains=search)
            | Q(title_ko__icontains=search)
            | Q(description__icontains=search)
            | Q(exam_number__icontains=search)
            | Q(paper_variant__icontains=search)
        )

    if level in [TopikExam.Level.TOPIK_I, TopikExam.Level.TOPIK_II]:
        queryset = queryset.filter(level=level)

    if request.user.is_authenticated:
        submitted_attempts = ExamAttempt.objects.filter(
            user=request.user,
            exam=OuterRef("pk"),
            status=ExamAttempt.Status.SUBMITTED,
        )
        queryset = queryset.annotate(is_completed=Exists(submitted_attempts))

        if status == "completed":
            queryset = queryset.filter(is_completed=True)
        elif status == "not_completed":
            queryset = queryset.filter(is_completed=False)

    if sort == "oldest":
        queryset = queryset.order_by("exam_number", "title")
    elif sort == "title":
        queryset = queryset.order_by("title")
    elif sort == "popular":
        queryset = queryset.order_by("-attempts_count", "-exam_number")
    else:
        queryset = queryset.order_by("-exam_number", "-created_at")

    return queryset, search, level, status, sort


def _render_exam_section_list(request, section_name, template_name, page_title, page_subtitle):
    exams = (
        TopikExam.objects.filter(
            is_active=True,
            sections__name=section_name,
            sections__is_active=True,
        )
        .distinct()
        .annotate(attempts_count=Count("attempts", distinct=True))
    )

    exams, search, level, status, sort = _filter_exam_list(exams, request)

    paginator = Paginator(exams, 9)
    page_obj = paginator.get_page(request.GET.get("page"))

    completed_count = 0
    pending_count = 0
    if request.user.is_authenticated:
        completed_count = exams.filter(is_completed=True).count()
        pending_count = exams.filter(is_completed=False).count()

    return render(request, template_name, {
        "page_obj": page_obj,
        "search": search,
        "level": level,
        "status": status,
        "sort": sort,
        "page_title": page_title,
        "page_subtitle": page_subtitle,
        "completed_count": completed_count,
        "pending_count": pending_count,
    })


def topik_mock_list(request):
    exams = (
        TopikExam.objects.filter(
            is_active=True,
            exam_mode=TopikExam.ExamMode.FULL,
        )
        .distinct()
        .annotate(
            attempts_count=Count("attempts", distinct=True),
            reading_materials_count=Count(
                "sections__materials",
                filter=Q(
                    sections__name=ExamSection.SectionType.READING,
                    sections__is_active=True,
                ),
                distinct=True,
            ),
        )
    )

    search = request.GET.get("search", "").strip()
    level = request.GET.get("level", "").strip()
    status = request.GET.get("status", "").strip()
    test_type = request.GET.get("type", "").strip()
    sort = request.GET.get("sort", "newest").strip()

    if search:
        exams = exams.filter(
            Q(title__icontains=search)
            | Q(title_ko__icontains=search)
            | Q(description__icontains=search)
            | Q(exam_number__icontains=search)
            | Q(paper_variant__icontains=search)
        )

    if level in [TopikExam.Level.TOPIK_I, TopikExam.Level.TOPIK_II]:
        exams = exams.filter(level=level)

    if request.user.is_authenticated:
        submitted_attempts = ExamAttempt.objects.filter(
            user=request.user,
            exam=OuterRef("pk"),
            status=ExamAttempt.Status.SUBMITTED,
        )
        exams = exams.annotate(is_completed=Exists(submitted_attempts))

        if status == "completed":
            exams = exams.filter(is_completed=True)
        elif status == "not_completed":
            exams = exams.filter(is_completed=False)

    if test_type == "grouped":
        exams = exams.filter(
            sections__name=ExamSection.SectionType.READING,
            sections__materials__display_type=ExamMaterial.DisplayType.GROUP,
            sections__materials__is_active=True,
        )
    elif test_type == "image":
        exams = exams.filter(
            Q(
                sections__name=ExamSection.SectionType.READING,
                sections__materials__image__isnull=False,
                sections__materials__is_active=True,
            )
            | Q(
                sections__name=ExamSection.SectionType.READING,
                sections__materials__material_type__in=[
                    ExamMaterial.MaterialType.TEXT_IMAGE,
                    ExamMaterial.MaterialType.IMAGE_ONLY,
                    ExamMaterial.MaterialType.MIXED,
                ],
                sections__materials__is_active=True,
            )
        )
    elif test_type == "mini":
        exams = exams.filter(
            sections__name=ExamSection.SectionType.READING,
            sections__total_questions__lte=20,
        )
    elif test_type == "full":
        exams = exams.filter(
            sections__name=ExamSection.SectionType.READING,
            sections__total_questions__gt=20,
        )

    exams = exams.distinct()

    if sort == "oldest":
        exams = exams.order_by("exam_number", "title")
    elif sort == "title":
        exams = exams.order_by("title")
    elif sort == "popular":
        exams = exams.order_by("-attempts_count", "-exam_number")
    else:
        exams = exams.order_by("-exam_number", "-created_at")

    paginator = Paginator(exams, 9)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "topik/components/exam_list.html", {
        "page_obj": page_obj,
        "search": search,
        "level": level,
        "status": status,
        "type": test_type,
        "sort": sort,
    })


def topik_reading_list(request):
    return _render_exam_section_list(
        request,
        ExamSection.SectionType.READING,
        "topik/components/exam_reading.html",
        "TOPIK Reading",
        "Practice all TOPIK exams that include a reading section.",
    )


def topik_listening_list(request):
    return _render_exam_section_list(
        request,
        ExamSection.SectionType.LISTENING,
        "topik/components/exam_listening.html",
        "TOPIK Listening",
        "Practice all TOPIK exams that include a listening section.",
    )


def topik_writing_list(request):
    return _render_exam_section_list(
        request,
        ExamSection.SectionType.WRITING,
        "topik/components/exam_writing.html",
        "TOPIK Writing",
        "Practice TOPIK writing tasks 51–54 with structured writing flow.",
    )


def topik_exam_detail(request, slug):
    exam = get_object_or_404(
        TopikExam.objects.prefetch_related("sections"),
        slug=slug,
        is_active=True,
    )
    return render(request, "topik/components/exam_detail.html", {"exam": exam})


def _build_section_context(attempt, section):
    saved_answers = {
        answer.question_id: answer
        for answer in attempt.answers.all()
    }

    saved_writing_submissions = {
        submission.task_id: submission
        for submission in attempt.writing_submissions.all()
    }

    writing_tasks = None
    if section.name == ExamSection.SectionType.WRITING:
        writing_tasks = section.writing_tasks.filter(is_active=True).order_by("task_number", "order")

    return {
        "saved_answers": saved_answers,
        "saved_writing_submissions": saved_writing_submissions,
        "writing_tasks": writing_tasks,
    }


@login_required
def _start_single_section_exam(request, slug, section_name):
    exam = get_object_or_404(
        TopikExam.objects.filter(
            is_active=True,
            sections__name=section_name,
            sections__is_active=True,
        ).distinct(),
        slug=slug,
    )

    active_attempt = ExamAttempt.objects.filter(
        user=request.user,
        exam=exam,
        status=ExamAttempt.Status.IN_PROGRESS,
    ).first()

    if active_attempt:
        return redirect(
            "topik:topik_exam_solve_section",
            attempt_id=active_attempt.id,
            section_name=section_name,
        )

    success, subscription = charge_test_usage(request.user, amount=1)
    if not success:
        return redirect("topik:topik_home")

    section = exam.sections.filter(
        is_active=True,
        name=section_name,
    ).order_by("order").first()

    attempt = ExamAttempt.objects.create(
        user=request.user,
        exam=exam,
        status=ExamAttempt.Status.IN_PROGRESS,
        current_section=section,
        current_section_started_at=timezone.now() if section else None,
    )

    return redirect(
        "topik:topik_exam_solve_section",
        attempt_id=attempt.id,
        section_name=section_name,
    )

@login_required
def start_topik_reading_exam(request, slug):
    return _start_single_section_exam(request, slug, ExamSection.SectionType.READING)


@login_required
def start_topik_listening_exam(request, slug):
    return _start_single_section_exam(request, slug, ExamSection.SectionType.LISTENING)


@login_required
def start_topik_writing_exam(request, slug):
    return _start_single_section_exam(request, slug, ExamSection.SectionType.WRITING)


@login_required
def start_topik_exam_section(request, slug, section_name):
    return _start_single_section_exam(request, slug, section_name)


@login_required
def start_topik_exam(request, slug):
    exam = get_object_or_404(TopikExam, slug=slug, is_active=True)

    active_attempt = ExamAttempt.objects.filter(
        user=request.user,
        exam=exam,
        status=ExamAttempt.Status.IN_PROGRESS,
    ).first()

    if active_attempt:
        if not active_attempt.current_section:
            first_section = exam.sections.filter(is_active=True).order_by("order").first()
            if first_section:
                active_attempt.current_section = first_section
                active_attempt.current_section_started_at = timezone.now()
                active_attempt.save(update_fields=["current_section", "current_section_started_at"])
        return redirect("topik:topik_exam_solve", attempt_id=active_attempt.id)

    success, subscription = charge_test_usage(request.user, amount=1)
    if not success:
        return redirect("topik:topik_home")

    first_section = exam.sections.filter(is_active=True).order_by("order").first()

    attempt = ExamAttempt.objects.create(
        user=request.user,
        exam=exam,
        status=ExamAttempt.Status.IN_PROGRESS,
        current_section=first_section,
        current_section_started_at=timezone.now() if first_section else None,
    )

    return redirect("topik:topik_exam_solve", attempt_id=attempt.id)
@login_required
def topik_exam_solve(request, attempt_id):
    attempt = get_object_or_404(
        ExamAttempt.objects.select_related("exam", "user", "current_section").prefetch_related(
            "exam__sections",
            "exam__sections__materials",
            "exam__sections__materials__questions",
            "exam__sections__materials__questions__choices",
            "exam__sections__writing_tasks",
            "exam__sections__writing_tasks__blanks",
            "answers",
            "writing_submissions",
        ),
        id=attempt_id,
        user=request.user,
    )

    if attempt.status == ExamAttempt.Status.SUBMITTED:
        return HttpResponseForbidden("This exam has already been submitted.")

    if not attempt.current_section:
        first_section = attempt.exam.sections.filter(is_active=True).order_by("order").first()
        if not first_section:
            return HttpResponseForbidden("This exam has no active sections.")
        attempt.current_section = first_section
        attempt.current_section_started_at = timezone.now()
        attempt.save(update_fields=["current_section", "current_section_started_at"])

    remaining_seconds = attempt.get_current_section_remaining_seconds()
    if remaining_seconds <= 0:
        return redirect("topik:advance_topik_exam_section", attempt_id=attempt.id)

    section = attempt.current_section
    sections = attempt.exam.sections.filter(id=section.id, is_active=True).order_by("order")

    all_sections = list(attempt.exam.sections.filter(is_active=True).order_by("order"))
    current_index = next((i for i, s in enumerate(all_sections) if s.id == section.id), 0)

    extra_context = _build_section_context(attempt, section)

    return render(
        request,
        "topik/components/exam_solve.html",
        {
            "attempt": attempt,
            "exam": attempt.exam,
            "sections": sections,
            "remaining_seconds": remaining_seconds,
            "main_section": section,
            "section_index": current_index + 1,
            "total_sections": len(all_sections),
            "active_section": section.name,
            **extra_context,
        },
    )


@login_required
def topik_exam_solve_section(request, attempt_id, section_name):
    attempt = get_object_or_404(
        ExamAttempt.objects.select_related("exam", "user", "current_section").prefetch_related(
            "exam__sections",
            "exam__sections__materials",
            "exam__sections__materials__questions",
            "exam__sections__materials__questions__choices",
            "exam__sections__writing_tasks",
            "exam__sections__writing_tasks__blanks",
            "answers",
            "writing_submissions",
        ),
        id=attempt_id,
        user=request.user,
    )

    if attempt.status == ExamAttempt.Status.SUBMITTED:
        return HttpResponseForbidden("This exam has already been submitted.")

    valid_sections = {
        ExamSection.SectionType.READING,
        ExamSection.SectionType.LISTENING,
        ExamSection.SectionType.WRITING,
    }

    if section_name not in valid_sections:
        return HttpResponseForbidden("Invalid section.")

    section = attempt.exam.sections.filter(
        is_active=True,
        name=section_name,
    ).order_by("order").first()

    if not section:
        return HttpResponseForbidden("This exam does not contain that section.")

    if not attempt.current_section or attempt.current_section.name != section_name:
        attempt.current_section = section
        attempt.current_section_started_at = timezone.now()
        attempt.save(update_fields=["current_section", "current_section_started_at"])

    remaining_seconds = attempt.get_current_section_remaining_seconds()
    if remaining_seconds <= 0:
        attempt.status = ExamAttempt.Status.EXPIRED
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=["status", "submitted_at"])
        return HttpResponseForbidden("Time is up. This section has expired.")

    sections = attempt.exam.sections.filter(id=section.id, is_active=True)
    extra_context = _build_section_context(attempt, section)

    return render(
        request,
        "topik/components/exam_solve.html",
        {
            "attempt": attempt,
            "exam": attempt.exam,
            "sections": sections,
            "remaining_seconds": remaining_seconds,
            "main_section": section,
            "section_index": 1,
            "total_sections": 1,
            "active_section": section.name,
            **extra_context,
        },
    )


@login_required
def advance_topik_exam_section(request, attempt_id):
    attempt = get_object_or_404(
        ExamAttempt.objects.select_related("exam", "current_section"),
        id=attempt_id,
        user=request.user,
        status=ExamAttempt.Status.IN_PROGRESS,
    )

    next_section = attempt.move_to_next_section()

    if next_section is None:
        return redirect("topik:finish_topik_exam", attempt_id=attempt.id)

    return redirect("topik:topik_exam_solve", attempt_id=attempt.id)


@login_required
@require_POST
def autosave_answer(request, attempt_id):
    attempt = get_object_or_404(
        ExamAttempt.objects.select_related("current_section"),
        id=attempt_id,
        user=request.user,
        status=ExamAttempt.Status.IN_PROGRESS,
    )

    if attempt.current_section and attempt.get_current_section_remaining_seconds() <= 0:
        return JsonResponse({"success": False, "message": "Current section expired."}, status=403)

    question_id = request.POST.get("question_id")
    choice_id = request.POST.get("choice_id")
    text_answer = request.POST.get("text_answer", "").strip()

    question = get_object_or_404(
        ExamQuestion.objects.select_related("material__section"),
        id=question_id,
    )

    if not attempt.current_section or question.material.section_id != attempt.current_section_id:
        return JsonResponse({"success": False, "message": "Question is not in the active section."}, status=400)

    answer, _ = ExamAnswer.objects.get_or_create(
        attempt=attempt,
        question=question,
    )

    if choice_id:
        choice = get_object_or_404(QuestionChoice, id=choice_id, question=question)
        answer.selected_choice = choice
        answer.text_answer = ""
    else:
        answer.selected_choice = None
        answer.text_answer = text_answer

    answer.save()

    return JsonResponse({"success": True})


@login_required
@require_POST
def autosave_writing_submission(request, attempt_id):
    attempt = get_object_or_404(
        ExamAttempt.objects.select_related("current_section"),
        id=attempt_id,
        user=request.user,
        status=ExamAttempt.Status.IN_PROGRESS,
    )

    if not attempt.current_section or attempt.current_section.name != ExamSection.SectionType.WRITING:
        return JsonResponse({"success": False, "message": "Writing section is not active."}, status=400)

    if attempt.get_current_section_remaining_seconds() <= 0:
        return JsonResponse({"success": False, "message": "Writing section expired."}, status=403)

    task_id = request.POST.get("task_id")
    answer_text = request.POST.get("answer_text", "").strip()

    task = get_object_or_404(
        WritingTask,
        id=task_id,
        section__exam=attempt.exam,
        section__id=attempt.current_section_id,
        section__name=ExamSection.SectionType.WRITING,
        is_active=True,
    )

    submission, _ = WritingSubmission.objects.get_or_create(
        attempt=attempt,
        task=task,
    )

    submission.answer_text = answer_text
    submission.save()

    return JsonResponse({
        "success": True,
        "word_count": submission.word_count,
    })


@login_required
@require_POST
def log_exam_event(request, attempt_id):
    attempt = get_object_or_404(
        ExamAttempt,
        id=attempt_id,
        user=request.user,
        status=ExamAttempt.Status.IN_PROGRESS,
    )

    event_type = request.POST.get("event_type")
    details = request.POST.get("details", "")

    valid_types = [choice[0] for choice in ExamEventLog.EventType.choices]
    if event_type not in valid_types:
        return JsonResponse({"success": False, "message": "Invalid event type"}, status=400)

    ExamEventLog.objects.create(
        attempt=attempt,
        event_type=event_type,
        details=details,
    )

    if event_type == ExamEventLog.EventType.TAB_SWITCH:
        attempt.tab_switch_count += 1
    elif event_type == ExamEventLog.EventType.FULLSCREEN_EXIT:
        attempt.fullscreen_exit_count += 1
    elif event_type == ExamEventLog.EventType.COPY_ATTEMPT:
        attempt.copy_attempt_count += 1
    elif event_type == ExamEventLog.EventType.PASTE_ATTEMPT:
        attempt.paste_attempt_count += 1
    elif event_type == ExamEventLog.EventType.RIGHT_CLICK:
        attempt.right_click_count += 1

    if (
        attempt.tab_switch_count >= 3
        or attempt.fullscreen_exit_count >= 3
        or attempt.copy_attempt_count >= 2
        or attempt.paste_attempt_count >= 2
    ):
        attempt.is_flagged = True

    attempt.save(update_fields=[
        "tab_switch_count",
        "fullscreen_exit_count",
        "copy_attempt_count",
        "paste_attempt_count",
        "right_click_count",
        "is_flagged",
    ])

    return JsonResponse({
        "success": True,
        "tab_switch_count": attempt.tab_switch_count,
        "fullscreen_exit_count": attempt.fullscreen_exit_count,
        "is_flagged": attempt.is_flagged,
    })


def finalize_attempt(attempt):
    if attempt.status != ExamAttempt.Status.IN_PROGRESS:
        return attempt

    if attempt.current_section and attempt.get_current_section_remaining_seconds() <= 0:
        attempt.status = ExamAttempt.Status.EXPIRED
    else:
        attempt.status = ExamAttempt.Status.SUBMITTED

    total_score = 0
    reading_score = 0
    listening_score = 0
    writing_score = 0

    # Objective sections
    for answer in attempt.answers.select_related(
        "question__material__section",
        "selected_choice",
    ):
        question = answer.question
        is_correct = False
        awarded = 0

        if question.question_type == question.QuestionType.SHORT_ANSWER:
            user_text = " ".join((answer.text_answer or "").strip().lower().split())
            correct_text = " ".join((question.correct_text_answer or "").strip().lower().split())
            is_correct = user_text == correct_text
        else:
            if answer.selected_choice:
                is_correct = answer.selected_choice.is_correct

        if is_correct:
            awarded = question.score

        answer.is_correct = is_correct
        answer.score_awarded = awarded
        answer.save(update_fields=["is_correct", "score_awarded"])

        total_score += awarded

        section_name = question.material.section.name
        if section_name == ExamSection.SectionType.READING:
            reading_score += awarded
        elif section_name == ExamSection.SectionType.LISTENING:
            listening_score += awarded

    # Writing section
    for submission in attempt.writing_submissions.select_related("task").prefetch_related("task__blanks"):
        scored_submission = score_writing_submission(submission)
        awarded = scored_submission.score_awarded or 0

        writing_score += awarded
        total_score += awarded

    attempt.total_score = total_score
    attempt.reading_score = reading_score
    attempt.listening_score = listening_score
    attempt.writing_score = writing_score
    attempt.submitted_at = timezone.now()

    attempt.save(update_fields=[
        "status",
        "submitted_at",
        "total_score",
        "reading_score",
        "listening_score",
        "writing_score",
    ])

    # ✅ save AI progress advice only once after submit
    if attempt.status == ExamAttempt.Status.SUBMITTED:
        try:
            update_progress_advice_for_user(attempt.user)
        except Exception as e:
            print("Progress advice update failed:", e)

    return attempt
@login_required
def topik_exam_result(request, attempt_id):
    attempt = get_object_or_404(
        ExamAttempt.objects.select_related("exam", "user").prefetch_related(
            "answers__question__material__section",
            "answers__selected_choice",
            "answers__question__choices",
            "writing_submissions__task",
            "writing_submissions__task__blanks",
        ),
        id=attempt_id,
        user=request.user,
    )

    answers = attempt.answers.all().order_by("question__question_number")
    writing_submissions = attempt.writing_submissions.all().order_by("task__task_number")

    total_questions = answers.count()
    correct_answers = answers.filter(is_correct=True).count()
    wrong_answers = total_questions - correct_answers
    accuracy = round((correct_answers / total_questions) * 100) if total_questions > 0 else 0

    grouped_answers = defaultdict(list)
    for answer in answers:
        section_name = answer.question.material.section.get_name_display()
        grouped_answers[section_name].append(answer)

    writing_total_score = sum((submission.score_awarded or 0) for submission in writing_submissions)

    context = {
        "attempt": attempt,
        "exam": attempt.exam,
        "answers": answers,
        "writing_submissions": writing_submissions,
        "grouped_answers": dict(grouped_answers),
        "total_questions": total_questions,
        "correct_answers": correct_answers,
        "wrong_answers": wrong_answers,
        "accuracy": accuracy,
        "writing_total_score": writing_total_score,
    }
    return render(request, "topik/components/exam_result.html", context)


@login_required
@require_POST
def submit_topik_exam(request, attempt_id):
    attempt = get_object_or_404(
        ExamAttempt,
        id=attempt_id,
        user=request.user,
    )

    if attempt.status != ExamAttempt.Status.IN_PROGRESS:
        return HttpResponseForbidden(f"This exam is not in progress. Current status: {attempt.status}")

    finalize_attempt(attempt)
    return redirect("topik:topik_exam_result", attempt_id=attempt.id)

@login_required
def finish_topik_exam(request, attempt_id):
    attempt = get_object_or_404(
        ExamAttempt,
        id=attempt_id,
        user=request.user,
        status=ExamAttempt.Status.IN_PROGRESS,
    )
    finalize_attempt(attempt)
    return redirect("topik:topik_exam_result", attempt_id=attempt.id)

@login_required
def topik_progress(request):
    user = request.user

    subscription = get_or_create_subscription(user)
    limits = subscription.get_limits()
    remaining_tests = max(0, limits["tests"] - subscription.tests_used_today)
    remaining_ai = max(0, limits["ai"] - subscription.ai_used_today)

    all_attempts = ExamAttempt.objects.filter(user=user)

    submitted_attempts = all_attempts.filter(
        status__in=[ExamAttempt.Status.SUBMITTED, ExamAttempt.Status.EVALUATED]
    ).select_related("exam").order_by("-submitted_at")

    topik1_attempts = submitted_attempts.filter(exam__level="TOPIK_I")
    topik2_attempts = submitted_attempts.filter(exam__level="TOPIK_II")

    total_attempts = all_attempts.count()
    completed_attempts = submitted_attempts.count()

    completion_rate = 0
    if total_attempts > 0:
        completion_rate = round((completed_attempts / total_attempts) * 100)

    average_score = round(submitted_attempts.aggregate(v=Avg("total_score"))["v"] or 0)
    best_score = round(submitted_attempts.aggregate(v=Max("total_score"))["v"] or 0)

    def build_chart_data(qs):
        labels, scores = [], []
        for a in reversed(list(qs[:6])):
            labels.append(a.submitted_at.strftime("%m/%d") if a.submitted_at else "N/A")
            scores.append(a.total_score or 0)
        return labels, scores

    t1_labels, t1_scores = build_chart_data(topik1_attempts)
    t2_labels, t2_scores = build_chart_data(topik2_attempts)

    reading_avg = round(submitted_attempts.aggregate(v=Avg("reading_score"))["v"] or 0)
    listening_avg = round(submitted_attempts.aggregate(v=Avg("listening_score"))["v"] or 0)
    writing_avg = round(submitted_attempts.aggregate(v=Avg("writing_score"))["v"] or 0)

    section_scores = {
        "Reading": reading_avg,
        "Listening": listening_avg,
        "Writing": writing_avg,
    }

    weakest_section = None
    strongest_section = None

    if completed_attempts > 0:
        weakest_section = min(section_scores, key=section_scores.get)
        strongest_section = max(section_scores, key=section_scores.get)

    recent_attempts = list(submitted_attempts[:6])

    progress_advice = {
        "summary": "",
        "focus_area": "",
        "advice_items": [],
        "updated_at": None,
    }

    insight = getattr(user, "topik_progress_insight", None)
    if insight:
        progress_advice = {
            "summary": insight.summary,
            "focus_area": insight.focus_area,
            "advice_items": insight.advice_items or [],
            "updated_at": insight.updated_at,
        }

    context = {
        "subscription": subscription,
        "remaining_tests": remaining_tests,
        "remaining_ai": remaining_ai,

        "total_attempts": total_attempts,
        "completed_attempts": completed_attempts,
        "completion_rate": completion_rate,

        "average_score": average_score,
        "best_score": best_score,

        "reading_avg": reading_avg,
        "listening_avg": listening_avg,
        "writing_avg": writing_avg,

        "weakest_section": weakest_section,
        "strongest_section": strongest_section,

        "topik1_labels": t1_labels,
        "topik1_scores": t1_scores,
        "topik2_labels": t2_labels,
        "topik2_scores": t2_scores,

        "recent_attempts": recent_attempts,
        "progress_advice": progress_advice,
    }

    return render(request, "topik/components/progress.html", context)




@login_required
def speaking_test_list(request):
    search = request.GET.get("search", "").strip()

    tests = SpeakingTest.objects.filter(is_active=True).annotate(
        question_count=Count("test_questions")
    )

    if search:
        tests = tests.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search)
        )

    tests = tests.order_by("-id")

    subscription = get_or_create_subscription(request.user)
    limits = subscription.get_limits()

    all_active_questions = SpeakingQuestion.objects.filter(is_active=True)

    context = {
        "tests": tests,
        "search": search,
        "credits_left": max(0, limits["tests"] - subscription.tests_used_today),
        "ai_left": max(0, limits["ai"] - subscription.ai_used_today),
        "subscription": subscription,
        "total_tests": tests.count(),
        "total_questions": all_active_questions.count(),
        "part1_count": all_active_questions.filter(part="PART1").count(),
        "part2_count": all_active_questions.filter(part="PART2").count(),
        "part3_count": all_active_questions.filter(part="PART3").count(),
    }
    return render(request, "topik/components/speaking_list.html", context)


@login_required
@require_http_methods(["POST"])
def start_speaking_test(request, test_id):
    test = get_object_or_404(SpeakingTest, id=test_id, is_active=True)

    existing_attempt = SpeakingAttempt.objects.filter(
        user=request.user,
        test=test,
        status=SpeakingAttempt.Status.IN_PROGRESS,
    ).first()

    if existing_attempt:
        return redirect("topik:speaking_test_room", attempt_id=existing_attempt.id)

    success, subscription = charge_test_usage(request.user, amount=1)
    if not success:
        return redirect("topik:speaking_test_list")

    attempt = SpeakingAttempt.objects.create(
        user=request.user,
        test=test,
        status=SpeakingAttempt.Status.IN_PROGRESS,
    )

    return redirect("topik:speaking_test_room", attempt_id=attempt.id)


@login_required
def speaking_test_room(request, attempt_id):
    attempt = get_object_or_404(
        SpeakingAttempt.objects.select_related("test", "user"),
        id=attempt_id,
        user=request.user,
    )

    if attempt.status != SpeakingAttempt.Status.IN_PROGRESS:
        return redirect("topik:speaking_result", attempt_id=attempt.id)

    test_questions = (
        SpeakingTestQuestion.objects
        .filter(test=attempt.test)
        .select_related("question")
        .order_by("order", "id")
    )

    existing_answers = {
        answer.question_id: answer
        for answer in attempt.answers.select_related("question")
    }

    questions_data = []
    for item in test_questions:
        q = item.question
        existing_answer = existing_answers.get(q.id)

        questions_data.append({
            "link_id": item.id,
            "question_id": q.id,
            "part": q.part,
            "part_display": q.get_part_display(),
            "question_type": q.question_type,
            "question_type_display": q.get_question_type_display(),
            "difficulty": q.difficulty,
            "difficulty_display": q.get_difficulty_display(),
            "title": q.title,
            "prompt": q.prompt,
            "follow_up_questions": q.follow_up_questions,
            "prep_time": q.prep_time,
            "speak_time": q.speak_time,
            "order": item.order,
            "has_answer": q.id in existing_answers,
            "saved_transcript": existing_answer.transcript if existing_answer else "",
            "saved_audio_url": existing_answer.audio_file.url if existing_answer and existing_answer.audio_file else "",
        })

    context = {
        "attempt": attempt,
        "test_questions": test_questions,
        "questions_data": questions_data,
        "total_questions": len(questions_data),
    }
    return render(request, "topik/components/speaking_test_room.html", context)


@login_required
@require_http_methods(["POST"])
def save_speaking_answer(request, attempt_id, question_id):
    attempt = get_object_or_404(
        SpeakingAttempt,
        id=attempt_id,
        user=request.user,
        status=SpeakingAttempt.Status.IN_PROGRESS,
    )

    question = get_object_or_404(
        SpeakingQuestion,
        id=question_id,
        is_active=True,
    )

    is_in_test = SpeakingTestQuestion.objects.filter(
        test=attempt.test,
        question=question,
    ).exists()

    if not is_in_test:
        return JsonResponse({
            "success": False,
            "error": "This question does not belong to the selected test.",
        }, status=400)

    transcript = request.POST.get("transcript", "").strip()
    audio_file = request.FILES.get("audio_file") or request.FILES.get("audio")

    if not transcript and not audio_file:
        return JsonResponse({
            "success": False,
            "error": "Please record audio or enter a transcript before saving.",
        }, status=400)

    answer, created = SpeakingAnswer.objects.get_or_create(
        attempt=attempt,
        question=question,
    )

    if audio_file:
        answer.audio_file = audio_file

    if transcript:
        answer.transcript = transcript

    answer.save()

    return JsonResponse({
        "success": True,
        "answer_id": answer.id,
        "question_id": question.id,
        "created": created,
        "audio_url": answer.audio_file.url if answer.audio_file else "",
        "transcript": answer.transcript or "",
    })


@login_required
@require_http_methods(["POST"])
def submit_speaking_test(request, attempt_id):
    attempt = get_object_or_404(
        SpeakingAttempt.objects.select_related("test", "user"),
        id=attempt_id,
        user=request.user,
        status=SpeakingAttempt.Status.IN_PROGRESS,
    )

    test_questions = (
        SpeakingTestQuestion.objects
        .filter(test=attempt.test)
        .select_related("question")
        .order_by("order", "id")
    )

    answers = {
        answer.question_id: answer
        for answer in attempt.answers.select_related("question")
    }

    missing_questions = [
        item.question.id
        for item in test_questions
        if item.question.id not in answers
        or (
            not (answers[item.question.id].transcript or "").strip()
            and not answers[item.question.id].audio_file
        )
    ]

    if missing_questions:
        return JsonResponse({
            "success": False,
            "error": "Please answer all questions before submitting.",
            "missing_question_ids": missing_questions,
        }, status=400)

    success, subscription = charge_ai_usage(request.user, amount=1)
    if not success:
        return JsonResponse({
            "success": False,
            "error": "Your daily AI evaluation limit has been reached.",
        }, status=400)

    try:
        attempt.status = SpeakingAttempt.Status.SUBMITTED
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=["status", "submitted_at"])

        evaluated_answers = attempt.answers.select_related("question").all()

        if not evaluated_answers.exists():
            refund_ai_usage(request.user, amount=1)
            return JsonResponse({
                "success": False,
                "error": "No answers found for this attempt.",
            }, status=400)

        for answer in evaluated_answers:
            if answer.audio_file and not (answer.transcript or "").strip():
                transcript = transcribe_speaking_audio(answer.audio_file.path)
                answer.transcript = transcript
                answer.save(update_fields=["transcript"])

            evaluate_speaking_answer(answer)

        evaluate_full_speaking_attempt(attempt)

        attempt.status = SpeakingAttempt.Status.EVALUATED
        attempt.evaluated_at = timezone.now()
        attempt.save(update_fields=[
            "status",
            "overall_score",
            "ai_feedback",
            "evaluated_at",
        ])

        return JsonResponse({
            "success": True,
            "redirect_url": reverse("topik:speaking_result", args=[attempt.id]),
        })

    except Exception as e:
        refund_ai_usage(request.user, amount=1)
        attempt.status = SpeakingAttempt.Status.SUBMITTED
        attempt.ai_feedback = {
            "feedback_summary": f"AI evaluation failed: {str(e)}"
        }
        attempt.save(update_fields=["status", "ai_feedback"])

        return JsonResponse({
            "success": False,
            "error": f"AI evaluation failed: {str(e)}",
        }, status=500)


@login_required
def speaking_result(request, attempt_id):
    attempt = get_object_or_404(
        SpeakingAttempt.objects.select_related("test", "user"),
        id=attempt_id,
        user=request.user,
    )

    answers = (
        attempt.answers
        .select_related("question")
        .order_by("id")
    )

    evaluated_attempts = (
        SpeakingAttempt.objects
        .filter(user=request.user, status=SpeakingAttempt.Status.EVALUATED)
        .select_related("test")
    )

    averages = evaluated_attempts.aggregate(
        average_overall=Avg("overall_score"),
    )

    answer_stats = (
        SpeakingAnswer.objects
        .filter(
            attempt__user=request.user,
            attempt__status=SpeakingAttempt.Status.EVALUATED,
        )
        .aggregate(
            average_fluency=Avg("fluency_score"),
            average_grammar=Avg("grammar_score"),
            average_vocab=Avg("vocabulary_score"),
            average_pronunciation=Avg("pronunciation_score"),
        )
    )

    recent_attempts = evaluated_attempts.exclude(id=attempt.id).order_by("-started_at")[:5]

    context = {
        "attempt": attempt,
        "answers": answers,
        "total_attempts": evaluated_attempts.count(),
        "average_overall": round(averages["average_overall"] or 0, 1),
        "average_fluency": round(answer_stats["average_fluency"] or 0, 1),
        "average_grammar": round(answer_stats["average_grammar"] or 0, 1),
        "average_vocab": round(answer_stats["average_vocab"] or 0, 1),
        "average_pronunciation": round(answer_stats["average_pronunciation"] or 0, 1),
        "recent_attempts": recent_attempts,
    }
    return render(request, "topik/components/speaking_result.html", context)


@login_required
@require_POST
def evaluate_topik_exam_ai(request, attempt_id):
    attempt = get_object_or_404(
        ExamAttempt.objects.select_related("exam", "user"),
        id=attempt_id,
        user=request.user,
    )

    if attempt.status not in [ExamAttempt.Status.SUBMITTED, ExamAttempt.Status.EVALUATED]:
        return JsonResponse({
            "success": False,
            "error": "Submit the exam before requesting AI evaluation.",
        }, status=400)

    if getattr(attempt, "ai_evaluated", False):
        return JsonResponse({
            "success": False,
            "error": "AI evaluation already completed for this attempt.",
        }, status=400)

    success, subscription = charge_ai_usage(request.user, amount=1)
    if not success:
        return JsonResponse({
            "success": False,
            "error": "Your daily AI evaluation limit has been reached.",
        }, status=400)

    try:
        feedback_parts = []

        if attempt.reading_score is not None:
            feedback_parts.append(
                f"Reading score: {attempt.reading_score}. "
                f"Focus on speed, keyword matching, and careful detail checking."
            )

        if attempt.listening_score is not None:
            feedback_parts.append(
                f"Listening score: {attempt.listening_score}. "
                f"Practice catching key words, numbers, and speaker intent."
            )

        if attempt.writing_score is not None:
            feedback_parts.append(
                f"Writing score: {attempt.writing_score}. "
                f"Work on structure, grammar accuracy, and clearer idea development."
            )

        feedback_parts.append(
            f"Total score: {attempt.total_score}. "
            f"Review your weakest section first and build consistency."
        )

        attempt.ai_feedback = {
            "feedback_parts": feedback_parts,
            "feedback_summary": " ".join(feedback_parts),
        }
        attempt.ai_evaluated = True
        attempt.ai_evaluated_at = timezone.now()
        attempt.status = ExamAttempt.Status.EVALUATED
        attempt.save(update_fields=[
            "ai_feedback",
            "ai_evaluated",
            "ai_evaluated_at",
            "status",
        ])

        return JsonResponse({
            "success": True
        })

    except Exception as e:
        refund_ai_usage(request.user, amount=1)
        return JsonResponse({
            "success": False,
            "error": f"AI evaluation failed: {str(e)}",
        }, status=500)