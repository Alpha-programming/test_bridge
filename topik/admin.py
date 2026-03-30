from django.contrib import admin
from django.forms.models import BaseInlineFormSet

from .models import *



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
    list_filter = (
        "level",
        "exam_type",
        "exam_mode",
        "is_active",
    )
    search_fields = (
        "title",
        "title_ko",
        "description",
        "exam_mode",
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
            "fields": (
                "created_at",
                "updated_at",
            ),
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
    list_filter = (
        "name",
        "exam__level",
        "exam__exam_type",
        "is_active",
    )
    search_fields = (
        "title",
        "instruction",
        "exam__title",
        "exam__title_ko",
    )
    list_editable = (
        "order",
        "total_questions",
        "duration_minutes",
        "is_active",
    )
    ordering = ("exam", "order")
    inlines = [ExamMaterialInline]
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Relation", {
            "fields": (
                "exam",
                "name",
                "title",
            )
        }),
        ("Section Content", {
            "fields": (
                "instruction",
                "audio_file",
            )
        }),
        ("Section Settings", {
            "fields": (
                "order",
                "total_questions",
                "duration_minutes",
                "is_active",
            )
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",),
        }),
    )

    def has_audio(self, obj):
        return bool(obj.audio_file)
    has_audio.short_description = "Audio"
    has_audio.boolean = True


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
    list_editable = (
        "order",
        "is_active",
    )
    ordering = ("section", "order")
    inlines = [ExamQuestionInline]
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Relation", {
            "fields": (
                "section",
            )
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
            "fields": (
                "start_number",
                "end_number",
            )
        }),
        ("Display", {
            "fields": (
                "order",
                "is_active",
            )
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",),
        }),
    )

    def title_or_fallback(self, obj):
        return obj.title or f"Material {obj.order}"
    title_or_fallback.short_description = "Title"

    def question_range(self, obj):
        if obj.start_number and obj.end_number:
            return f"{obj.start_number}-{obj.end_number}"
        if obj.start_number:
            return str(obj.start_number)
        return "-"
    question_range.short_description = "Q Range"


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
    list_editable = (
        "score",
        "difficulty",
        "is_active",
    )
    ordering = ("question_number", "order")
    inlines = [QuestionChoiceInline]
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Relation", {
            "fields": (
                "material",
            )
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
            "fields": (
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",),
        }),
    )

    def short_question_text(self, obj):
        return obj.question_text[:80] if obj.question_text else "-"
    short_question_text.short_description = "Question"

    def exam_title(self, obj):
        return obj.material.section.exam.title
    exam_title.short_description = "Exam"

    def section_name(self, obj):
        return obj.material.section.get_name_display()
    section_name.short_description = "Section"

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
    list_editable = (
        "is_correct",
        "order",
    )
    ordering = ("question__question_number", "order")

    def question_number(self, obj):
        return obj.question.question_number
    question_number.short_description = "Q No"

    def exam_title(self, obj):
        return obj.question.material.section.exam.title
    exam_title.short_description = "Exam"

    def short_choice_text(self, obj):
        return obj.choice_text[:60] if obj.choice_text else "[Image Choice]"
    short_choice_text.short_description = "Choice"


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "exam",
        "status",
        "current_section_started_at",
        "total_score",
        "listening_score",
        "reading_score",
        "tab_switch_count",
        "fullscreen_exit_count",
        "is_flagged",
        "started_at",
        "submitted_at",
    )
    list_filter = (
        "status",
        "is_flagged",
        "exam__level",
        "exam__exam_type",
    )
    search_fields = (
        "user__username",
        "user__email",
        "exam__title",
    )
    readonly_fields = (
        "started_at",
        "submitted_at",
        "created_at",
        "updated_at",
    )
    ordering = ("-started_at",)

    fieldsets = (
        ("Relation", {
            "fields": (
                "user",
                "current_section_started_at",
                "exam",
                "status",
                "is_flagged",
            )
        }),
        ("Scores", {
            "fields": (
                "total_score",
                "listening_score",
                "reading_score",
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
    list_display = (
        "id",
        "attempt",
        "event_type",
        "short_details",
        "created_at",
    )
    list_filter = (
        "event_type",
        "created_at",
        "attempt__exam__level",
        "attempt__is_flagged",
    )
    search_fields = (
        "attempt__user__username",
        "attempt__user__email",
        "attempt__exam__title",
        "details",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)

    def short_details(self, obj):
        return obj.details[:80] if obj.details else "-"
    short_details.short_description = "Details"
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
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    ordering = ("attempt", "question__question_number")

    def question_number(self, obj):
        return obj.question.question_number
    question_number.short_description = "Q No"

    def section_name(self, obj):
        return obj.question.material.section.get_name_display()
    section_name.short_description = "Section"

class WritingTaskBlankInline(admin.TabularInline):
    model = WritingTaskBlank
    extra = 0
    fields = ("blank_order", "answer_label", "correct_answer")
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
    list_editable = (
        "score",
        "order",
        "is_active",
    )
    ordering = ("task_number", "order")
    inlines = [WritingTaskBlankInline]
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Relation", {
            "fields": (
                "section",
                "task_number",
                "task_type",
                "order",
            )
        }),
        ("Content", {
            "fields": (
                "title",
                "instruction",
                "prompt",
                "image",
            )
        }),
        ("Task Settings", {
            "fields": (
                "min_words",
                "max_words",
                "score",
                "is_active",
            )
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",),
        }),
    )

    def title_or_fallback(self, obj):
        return obj.title or f"Writing Task {obj.task_number}"
    title_or_fallback.short_description = "Title"
@admin.register(WritingTaskBlank)
class WritingTaskBlankAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "task",
        "blank_order",
        "answer_label",
        "correct_answer",
        "scoring_note"
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
    readonly_fields = (
        "word_count",
        "created_at",
        "updated_at",
    )
    ordering = ("attempt", "task__task_number")

    fieldsets = (
        ("Relation", {
            "fields": (
                "attempt",
                "task",
            )
        }),
        ("Submission", {
            "fields": (
                "answer_text",
                "word_count",
            )
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
            "fields": (
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",),
        }),
    )

    def task_number(self, obj):
        return obj.task.task_number
    task_number.short_description = "Task No"

    def task_type(self, obj):
        return obj.task.get_task_type_display()
    task_type.short_description = "Task Type"