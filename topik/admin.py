from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from .models import (
    TopikExam,
    ExamSection,
    ExamMaterial,
    ExamQuestion,
    QuestionChoice,
    ExamAttempt,
    ExamAnswer,
    ExamEventLog,
    WritingTask,
    WritingTaskBlank,
    WritingSubmission,
    UserProgressInsight,
    SpeakingQuestion,
    SpeakingTest,
    SpeakingTestQuestion,
    SpeakingAttempt,
    SpeakingAnswer,
)


# =========================
# QUESTION CHOICES
# =========================
class QuestionChoiceInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        question = self.instance
        if not question:
            return

        choice_required_types = {
            ExamQuestion.QuestionType.MCQ_SINGLE,
            ExamQuestion.QuestionType.TRUE_FALSE,
            ExamQuestion.QuestionType.MATCHING,
            ExamQuestion.QuestionType.ORDERING,
        }

        if question.question_type not in choice_required_types:
            return

        valid_choices_count = 0
        correct_count = 0

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue

            if form.cleaned_data.get("DELETE", False):
                continue

            choice_text = form.cleaned_data.get("choice_text")
            image = form.cleaned_data.get("image")
            is_correct = form.cleaned_data.get("is_correct", False)

            if not choice_text and not image:
                continue

            valid_choices_count += 1
            if is_correct:
                correct_count += 1

        if valid_choices_count == 0:
            raise ValidationError("This question type requires at least one choice.")

        if correct_count == 0:
            raise ValidationError("This question must have at least one correct choice.")


class QuestionChoiceInline(admin.TabularInline):
    model = QuestionChoice
    formset = QuestionChoiceInlineFormSet
    extra = 4
    fields = ("order", "label", "choice_text", "image", "is_correct")
    ordering = ("order",)


# =========================
# TOPIK EXAM
# =========================
class ExamQuestionInline(admin.TabularInline):
    model = ExamQuestion
    extra = 0
    fields = (
        "question_number",
        "order",
        "question_text",
        "question_type",
        "score",
        "difficulty",
        "is_active",
    )
    ordering = ("question_number", "order")


class ExamMaterialInline(admin.TabularInline):
    model = ExamMaterial
    extra = 0
    fields = (
        "order",
        "title",
        "material_type",
        "display_type",
        "start_number",
        "end_number",
        "is_active",
    )
    ordering = ("order",)


@admin.register(TopikExam)
class TopikExamAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "level",
        "exam_type",
        "exam_mode",
        "exam_number",
        "paper_variant",
        "duration_minutes",
        "total_questions",
        "is_active",
        "created_at",
    )
    list_filter = ("level", "exam_type", "exam_mode", "is_active")
    search_fields = (
        "title",
        "title_ko",
        "description",
        "paper_variant",
        "slug",
    )
    list_editable = ("is_active",)
    ordering = ("-exam_number", "title")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Basic Info", {
            "fields": (
                "title",
                "title_ko",
                "slug",
                "level",
                "exam_type",
                "exam_mode",
                "exam_number",
                "paper_variant",
            )
        }),
        ("Exam Settings", {
            "fields": (
                "duration_minutes",
                "total_questions",
                "description",
                "is_active",
            )
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(ExamSection)
class ExamSectionAdmin(admin.ModelAdmin):
    list_display = (
        "exam",
        "name",
        "title",
        "order",
        "total_questions",
        "duration_minutes",
        "has_audio",
        "is_active",
    )
    list_filter = ("name", "exam__level", "exam__exam_type", "is_active")
    search_fields = ("title", "instruction", "exam__title", "exam__title_ko")
    list_editable = ("order", "total_questions", "duration_minutes", "is_active")
    ordering = ("exam", "order")
    inlines = [ExamMaterialInline]
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Relation", {
            "fields": ("exam", "name", "title")
        }),
        ("Section Content", {
            "fields": ("instruction", "audio_file")
        }),
        ("Section Settings", {
            "fields": ("order", "total_questions", "duration_minutes", "is_active")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(boolean=True, description="Audio")
    def has_audio(self, obj):
        return bool(obj.audio_file)


@admin.register(ExamMaterial)
class ExamMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title_or_fallback",
        "section",
        "material_type",
        "display_type",
        "question_range",
        "order",
        "is_active",
    )
    list_filter = (
        "section__name",
        "section__exam__level",
        "section__exam",
        "material_type",
        "display_type",
        "is_active",
    )
    search_fields = (
        "title",
        "instruction",
        "content_text",
        "section__title",
        "section__exam__title",
        "section__exam__title_ko",
    )
    list_editable = ("order", "is_active")
    ordering = ("section", "order")
    inlines = [ExamQuestionInline]
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Relation", {
            "fields": ("section",)
        }),
        ("Content", {
            "fields": (
                "title",
                "instruction",
                "material_type",
                "display_type",
                "content_text",
                "image",
            )
        }),
        ("Question Range", {
            "fields": ("start_number", "end_number")
        }),
        ("Display", {
            "fields": ("order", "is_active")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Title")
    def title_or_fallback(self, obj):
        return obj.title or f"Material {obj.order}"

    @admin.display(description="Q Range")
    def question_range(self, obj):
        if obj.start_number and obj.end_number:
            return f"{obj.start_number}-{obj.end_number}"
        if obj.start_number:
            return str(obj.start_number)
        return "-"


@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "question_number",
        "short_question_text",
        "section_name",
        "exam_title",
        "question_type",
        "score",
        "difficulty",
        "is_active",
    )
    list_filter = (
        "material__section__name",
        "material__section__exam__level",
        "material__section__exam",
        "question_type",
        "difficulty",
        "is_active",
    )
    search_fields = (
        "question_text",
        "explanation",
        "correct_text_answer",
        "material__title",
        "material__content_text",
        "material__section__exam__title",
    )
    list_editable = ("score", "difficulty", "is_active")
    ordering = ("question_number", "order")
    inlines = [QuestionChoiceInline]
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Relation", {
            "fields": ("material",)
        }),
        ("Question", {
            "fields": (
                "question_number",
                "order",
                "question_text",
                "question_type",
                "image",
            )
        }),
        ("Scoring", {
            "fields": (
                "score",
                "difficulty",
                "correct_text_answer",
                "explanation",
                "is_active",
            )
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Question")
    def short_question_text(self, obj):
        return obj.question_text[:80] if obj.question_text else "-"

    @admin.display(description="Exam")
    def exam_title(self, obj):
        return obj.material.section.exam.title

    @admin.display(description="Section")
    def section_name(self, obj):
        return obj.material.section.get_name_display()

    def save_model(self, request, obj, form, change):
        if (
            obj.question_type == ExamQuestion.QuestionType.SHORT_ANSWER
            and not obj.correct_text_answer
        ):
            raise ValidationError("Short answer questions require correct_text_answer.")
        super().save_model(request, obj, form, change)


@admin.register(QuestionChoice)
class QuestionChoiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "question_number",
        "exam_title",
        "label",
        "short_choice_text",
        "is_correct",
        "order",
    )
    list_filter = (
        "is_correct",
        "question__material__section__name",
        "question__material__section__exam__level",
        "question__question_type",
    )
    search_fields = (
        "choice_text",
        "question__question_text",
        "question__material__section__exam__title",
    )
    list_editable = ("is_correct", "order")
    ordering = ("question__question_number", "order")

    @admin.display(description="Q No")
    def question_number(self, obj):
        return obj.question.question_number

    @admin.display(description="Exam")
    def exam_title(self, obj):
        return obj.question.material.section.exam.title

    @admin.display(description="Choice")
    def short_choice_text(self, obj):
        return obj.choice_text[:60] if obj.choice_text else "[Image Choice]"


# =========================
# EXAM ATTEMPT / ANSWERS
# =========================
@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "exam",
        "status",
        "current_section",
        "total_score",
        "listening_score",
        "reading_score",
        "writing_score",
        "ai_evaluated",
        "is_flagged",
        "started_at",
        "submitted_at",
    )
    list_filter = (
        "status",
        "ai_evaluated",
        "is_flagged",
        "exam__level",
        "exam__exam_type",
    )
    search_fields = ("user__username", "user__email", "exam__title")
    readonly_fields = (
        "started_at",
        "submitted_at",
        "created_at",
        "updated_at",
        "ai_evaluated_at",
    )
    ordering = ("-started_at",)

    fieldsets = (
        ("Relation", {
            "fields": (
                "user",
                "exam",
                "status",
                "current_section",
                "current_section_started_at",
                "is_flagged",
            )
        }),
        ("Scores", {
            "fields": (
                "total_score",
                "listening_score",
                "reading_score",
                "writing_score",
            )
        }),
        ("AI Evaluation", {
            "fields": (
                "ai_evaluated",
                "ai_feedback",
                "ai_evaluated_at",
            )
        }),
        ("Monitoring", {
            "fields": (
                "tab_switch_count",
                "fullscreen_exit_count",
                "copy_attempt_count",
                "paste_attempt_count",
                "right_click_count",
            )
        }),
        ("Timing", {
            "fields": (
                "started_at",
                "submitted_at",
                "created_at",
                "updated_at",
            )
        }),
    )


@admin.register(ExamEventLog)
class ExamEventLogAdmin(admin.ModelAdmin):
    list_display = ("id", "attempt", "event_type", "short_details", "created_at")
    list_filter = ("event_type", "created_at", "attempt__exam__level", "attempt__is_flagged")
    search_fields = (
        "attempt__user__username",
        "attempt__user__email",
        "attempt__exam__title",
        "details",
    )
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)

    @admin.display(description="Details")
    def short_details(self, obj):
        return obj.details[:80] if obj.details else "-"


@admin.register(ExamAnswer)
class ExamAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "attempt",
        "question_number",
        "section_name",
        "selected_choice",
        "text_answer",
        "is_correct",
        "score_awarded",
    )
    list_filter = (
        "is_correct",
        "question__material__section__name",
        "question__material__section__exam__level",
    )
    search_fields = (
        "attempt__user__username",
        "attempt__exam__title",
        "question__question_text",
        "text_answer",
    )
    readonly_fields = ("created_at", "updated_at")
    ordering = ("attempt", "question__question_number")

    @admin.display(description="Q No")
    def question_number(self, obj):
        return obj.question.question_number

    @admin.display(description="Section")
    def section_name(self, obj):
        return obj.question.material.section.get_name_display()


# =========================
# WRITING
# =========================
class WritingTaskBlankInline(admin.TabularInline):
    model = WritingTaskBlank
    extra = 0
    fields = ("blank_order", "answer_label", "correct_answer", "scoring_note")
    ordering = ("blank_order",)


@admin.register(WritingTask)
class WritingTaskAdmin(admin.ModelAdmin):
    list_display = (
        "task_number",
        "title_or_fallback",
        "task_type",
        "section",
        "score",
        "min_words",
        "max_words",
        "order",
        "is_active",
    )
    list_filter = (
        "task_type",
        "section__exam__level",
        "section__exam__exam_type",
        "section__exam__exam_mode",
        "is_active",
    )
    search_fields = (
        "title",
        "instruction",
        "prompt",
        "section__title",
        "section__exam__title",
        "section__exam__title_ko",
    )
    list_editable = ("score", "order", "is_active")
    ordering = ("task_number", "order")
    inlines = [WritingTaskBlankInline]
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Relation", {
            "fields": ("section", "task_number", "task_type", "order")
        }),
        ("Content", {
            "fields": ("title", "instruction", "prompt", "image")
        }),
        ("Task Settings", {
            "fields": ("min_words", "max_words", "score", "is_active")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Title")
    def title_or_fallback(self, obj):
        return obj.title or f"Writing Task {obj.task_number}"


@admin.register(WritingTaskBlank)
class WritingTaskBlankAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "task",
        "blank_order",
        "answer_label",
        "correct_answer",
        "scoring_note",
    )
    list_filter = (
        "task__task_type",
        "task__section__exam__level",
        "task__section__exam__exam_type",
    )
    search_fields = (
        "answer_label",
        "correct_answer",
        "task__title",
        "task__prompt",
        "task__section__exam__title",
    )
    ordering = ("task__task_number", "blank_order")


@admin.register(WritingSubmission)
class WritingSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "attempt",
        "task_number",
        "task_type",
        "word_count",
        "score_awarded",
        "ai_score",
        "final_score",
        "is_correct",
        "created_at",
    )
    list_filter = (
        "task__task_type",
        "task__section__exam__level",
        "task__section__exam__exam_type",
        "is_correct",
    )
    search_fields = (
        "attempt__user__username",
        "attempt__user__email",
        "attempt__exam__title",
        "task__prompt",
        "answer_text",
    )
    readonly_fields = ("word_count", "created_at", "updated_at")
    ordering = ("attempt", "task__task_number")

    fieldsets = (
        ("Relation", {
            "fields": ("attempt", "task")
        }),
        ("Submission", {
            "fields": ("answer_text", "word_count")
        }),
        ("Scoring", {
            "fields": (
                "is_correct",
                "score_awarded",
                "ai_score",
                "final_score",
                "ai_feedback",
            )
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Task No")
    def task_number(self, obj):
        return obj.task.task_number

    @admin.display(description="Task Type")
    def task_type(self, obj):
        return obj.task.get_task_type_display()


@admin.register(UserProgressInsight)
class UserProgressInsightAdmin(admin.ModelAdmin):
    list_display = ("user", "focus_area", "based_on_attempt_count", "updated_at")
    search_fields = ("user__username", "user__email", "focus_area")
    readonly_fields = ("updated_at",)
    list_filter = ("focus_area", "updated_at")


# =========================
# SPEAKING
# =========================
class SpeakingTestQuestionInline(admin.TabularInline):
    model = SpeakingTestQuestion
    extra = 1
    autocomplete_fields = ["question"]
    ordering = ["order"]


@admin.register(SpeakingQuestion)
class SpeakingQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "short_title",
        "part",
        "question_type",
        "difficulty",
        "prep_time",
        "speak_time",
        "is_active",
        "order",
        "created_at",
    )
    list_filter = ("part", "question_type", "difficulty", "is_active", "created_at")
    search_fields = ("title", "prompt")
    list_editable = ("is_active", "order", "prep_time", "speak_time")
    ordering = ("part", "order", "id")

    fieldsets = (
        ("Basic Info", {
            "fields": ("part", "question_type", "difficulty", "is_active", "order")
        }),
        ("Question Content", {
            "fields": ("title", "prompt", "follow_up_questions")
        }),
        ("Timing", {
            "fields": ("prep_time", "speak_time")
        }),
        ("Extra", {
            "fields": ("sample_answer", "tags")
        }),
    )

    @admin.display(description="Title / Prompt")
    def short_title(self, obj):
        return obj.title or obj.prompt[:50]


@admin.register(SpeakingTest)
class SpeakingTestAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "is_active", "question_count", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("title", "description")
    list_editable = ("is_active",)
    inlines = [SpeakingTestQuestionInline]

    fieldsets = (
        ("Test Info", {
            "fields": ("title", "description", "is_active")
        }),
    )

    @admin.display(description="Questions")
    def question_count(self, obj):
        return obj.test_questions.count()


@admin.register(SpeakingTestQuestion)
class SpeakingTestQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "test", "question", "order")
    list_filter = ("test", "question__part", "question__question_type")
    search_fields = ("test__title", "question__title", "question__prompt")
    list_editable = ("order",)
    autocomplete_fields = ["test", "question"]
    ordering = ("test", "order", "id")


class SpeakingAnswerInline(admin.TabularInline):
    model = SpeakingAnswer
    extra = 0
    can_delete = False
    readonly_fields = (
        "question",
        "audio_file",
        "transcript",
        "ai_score",
        "grammar_score",
        "fluency_score",
        "vocabulary_score",
        "pronunciation_score",
        "task_completion_score",
        "ai_feedback",
        "created_at",
    )
    fields = (
        "question",
        "audio_file",
        "transcript",
        "ai_score",
        "grammar_score",
        "fluency_score",
        "vocabulary_score",
        "pronunciation_score",
        "task_completion_score",
        "ai_feedback",
        "created_at",
    )


@admin.register(SpeakingAttempt)
class SpeakingAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "test",
        "status",
        "overall_score",
        "started_at",
        "submitted_at",
        "evaluated_at",
    )
    list_filter = ("status", "test", "started_at", "submitted_at", "evaluated_at")
    search_fields = ("user__username", "user__email", "test__title")
    readonly_fields = (
        "started_at",
        "submitted_at",
        "evaluated_at",
        "overall_score",
        "ai_feedback",
    )
    autocomplete_fields = ["user", "test"]
    inlines = [SpeakingAnswerInline]
    ordering = ("-started_at",)

    fieldsets = (
        ("Basic Info", {
            "fields": ("user", "test", "status")
        }),
        ("Evaluation", {
            "fields": ("overall_score", "ai_feedback")
        }),
        ("Timing", {
            "fields": ("started_at", "submitted_at", "evaluated_at")
        }),
    )


@admin.register(SpeakingAnswer)
class SpeakingAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "attempt",
        "question",
        "ai_score",
        "grammar_score",
        "fluency_score",
        "vocabulary_score",
        "pronunciation_score",
        "task_completion_score",
        "created_at",
    )
    list_filter = ("question__part", "question__question_type", "created_at")
    search_fields = (
        "question__title",
        "question__prompt",
        "attempt__user__username",
        "attempt__test__title",
        "transcript",
    )
    readonly_fields = ("created_at",)
    autocomplete_fields = ["attempt", "question"]

    fieldsets = (
        ("Basic Info", {
            "fields": ("attempt", "question", "audio_file")
        }),
        ("Transcript", {
            "fields": ("transcript",)
        }),
        ("AI Evaluation", {
            "fields": (
                "ai_score",
                "grammar_score",
                "fluency_score",
                "vocabulary_score",
                "pronunciation_score",
                "task_completion_score",
                "ai_feedback",
            )
        }),
        ("Time", {
            "fields": ("created_at",)
        }),
    )