from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    TopikExam,
    ExamAttempt,
    ExamAnswer,
    ExamSection,
    ExamMaterial,
    ExamQuestion,
    QuestionChoice,
    ExamEventLog,
    WritingTask,
    WritingSubmission,
)
from .services.writing_scoring import score_writing_submission


def topik_home(request):
    featured_exams = TopikExam.objects.filter(is_active=True).order_by("-exam_number")[:3]
    return render(request, "topik/main.html", {"featured_exams": featured_exams})


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
        status=ExamAttempt.Status.IN_PROGRESS,
    )
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