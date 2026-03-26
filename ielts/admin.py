from django.contrib import admin
from .models import (
    ReadingTest,
    Passage,
    Paragraph,
    QuestionGroup,
    Question,
    Option,
    UserReadingTest,
    UserAnswer,
    Subscription
)


# =========================
# 🔹 PARAGRAPH INLINE
# =========================
class ParagraphInline(admin.TabularInline):
    model = Paragraph
    extra = 1
    fields = ("label", "content", "order")
    ordering = ("order",)


# =========================
# 🔹 OPTION INLINE (FOR QUESTION)
# =========================
class OptionInline(admin.TabularInline):
    model = Option
    extra = 2
    fields = ("label", "text", "is_correct")
    ordering = ("label",)
    fk_name = "question"


# =========================
# 🔹 GROUP OPTION INLINE
# =========================
class GroupOptionInline(admin.TabularInline):
    model = Option
    extra = 2
    fields = ("label", "text")
    ordering = ("label",)
    fk_name = "group"


# =========================
# 🔹 QUESTION ADMIN
# =========================
@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["number", "group", "get_passage", "correct_answer"]
    ordering = ["number"]
    search_fields = ["text"]
    list_filter = ["group__group_type", "group__passage__test"]

    inlines = [OptionInline]

    def get_passage(self, obj):
        return obj.group.passage
    get_passage.short_description = "Passage"


# =========================
# 🔹 QUESTION INLINE
# =========================
class QuestionInline(admin.TabularInline):
    model = Question
    extra = 2
    fields = ("number", "text", "correct_answer")
    show_change_link = True
    ordering = ("number",)


# =========================
# 🔹 QUESTION GROUP ADMIN
# =========================
@admin.register(QuestionGroup)
class QuestionGroupAdmin(admin.ModelAdmin):
    list_display = ["title", "group_type", "passage", "order"]
    list_filter = ["group_type", "passage__test"]
    search_fields = ["title", "instruction"]

    ordering = ["order"]
    save_on_top = True

    fieldsets = (
        ("Basic Info", {
            "fields": ("passage", "title", "group_type", "order")
        }),
        ("Instruction", {
            "fields": ("instruction",),
        }),
        ("Optional", {
            "fields": ("diagram_image",),
            "classes": ("collapse",)
        }),
    )

    inlines = [
        QuestionInline,
        GroupOptionInline
    ]


# =========================
# 🔹 PASSAGE ADMIN
# =========================
@admin.register(Passage)
class PassageAdmin(admin.ModelAdmin):
    list_display = ["title", "subtitle", "test", "order"]
    list_filter = ["test"]
    search_fields = ["title", "content"]
    ordering = ["order"]

    save_on_top = True

    fieldsets = (
        ("Basic Info", {
            "fields": ("test", "title", "subtitle", "order")
        }),
        ("Content (Optional)", {
            "fields": ("content",),
            "classes": ("collapse",)
        }),
    )

    inlines = [ParagraphInline]


# =========================
# 🔹 READING TEST ADMIN
# =========================
@admin.register(ReadingTest)
class ReadingTestAdmin(admin.ModelAdmin):
    list_display = ["title", "duration_minutes", "created_at"]
    search_fields = ["title"]
    ordering = ["-created_at"]
    save_on_top = True


# =========================
# 🔹 USER ANSWER INLINE
# =========================
class UserAnswerInline(admin.TabularInline):
    model = UserAnswer
    extra = 0
    readonly_fields = ("question", "answer", "is_correct", "created_at")


# =========================
# 🔹 USER TEST ADMIN
# =========================
@admin.register(UserReadingTest)
class UserReadingTestAdmin(admin.ModelAdmin):
    list_display = ["user", "test", "score", "started_at", "completed_at"]
    list_filter = ["test", "completed_at"]
    search_fields = ["user__username"]

    readonly_fields = ("started_at", "completed_at", "answers_json")

    inlines = [UserAnswerInline]


# =========================
# 🔹 USER ANSWER ADMIN
# =========================
@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ["user", "question", "answer", "is_correct", "created_at"]
    list_filter = ["is_correct", "test"]
    search_fields = ["user__username", "question__text"]


# =========================
# 🔹 OPTION ADMIN (SAFE)
# =========================
@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ["label", "text", "question", "group", "is_correct"]
    list_filter = ["question", "group"]


from django.contrib import admin
from .models import (
    ListeningTest,
    ListeningSection,
    ListeningGroup,
    ListeningQuestion,
    ListeningOption,
    UserListeningTest,
    UserListeningAnswer
)

# =========================
# 🔘 OPTION INLINE
# =========================
class ListeningOptionInline(admin.TabularInline):
    model = ListeningOption
    extra = 2


# =========================
# ❓ QUESTION INLINE
# =========================
class ListeningQuestionInline(admin.TabularInline):
    model = ListeningQuestion
    extra = 2


# =========================
# 📦 GROUP ADMIN
# =========================
@admin.register(ListeningGroup)
class ListeningGroupAdmin(admin.ModelAdmin):
    list_display = ("section", "group_type", "order")
    list_filter = ("group_type",)
    inlines = [ListeningQuestionInline]


# =========================
# 📄 SECTION ADMIN
# =========================
class ListeningGroupInline(admin.TabularInline):
    model = ListeningGroup
    extra = 1


@admin.register(ListeningSection)
class ListeningSectionAdmin(admin.ModelAdmin):
    list_display = ("test", "title", "order")
    inlines = [ListeningGroupInline]


# =========================
# 🎧 TEST ADMIN
# =========================
class ListeningSectionInline(admin.TabularInline):
    model = ListeningSection
    extra = 1


@admin.register(ListeningTest)
class ListeningTestAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at")
    inlines = [ListeningSectionInline]


# =========================
# ❓ QUESTION ADMIN (FULL)
# =========================
@admin.register(ListeningQuestion)
class ListeningQuestionAdmin(admin.ModelAdmin):
    list_display = ("number", "group")
    inlines = [ListeningOptionInline]


# =========================
# 👤 USER TEST
# =========================
@admin.register(UserListeningTest)
class UserListeningTestAdmin(admin.ModelAdmin):
    list_display = ("user", "test", "score", "completed_at")
    list_filter = ("completed_at",)


# =========================
# ✍️ USER ANSWER
# =========================
@admin.register(UserListeningAnswer)
class UserListeningAnswerAdmin(admin.ModelAdmin):
    list_display = ("user_test", "question", "answer", "is_correct")
    list_filter = ("is_correct",)


from .models import (
    WritingTest,
    WritingTask1,
    WritingTask2,
    UserWritingTest,
    WritingResult
)


# =========================
# 📘 Writing Test
# =========================
class WritingTask1Inline(admin.StackedInline):
    model = WritingTask1
    extra = 0


class WritingTask2Inline(admin.StackedInline):
    model = WritingTask2
    extra = 0


@admin.register(WritingTest)
class WritingTestAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "duration_minutes", "created_at")
    search_fields = ("title",)
    list_filter = ("created_at",)

    inlines = [WritingTask1Inline, WritingTask2Inline]


# =========================
# 📝 Task 1
# =========================
@admin.register(WritingTask1)
class WritingTask1Admin(admin.ModelAdmin):
    list_display = ("id", "test")
    search_fields = ("test__title",)


# =========================
# 📝 Task 2
# =========================
@admin.register(WritingTask2)
class WritingTask2Admin(admin.ModelAdmin):
    list_display = ("id", "test")
    search_fields = ("test__title",)


# =========================
# 👤 User Writing Attempts
# =========================
@admin.register(UserWritingTest)
class UserWritingTestAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "test", "started_at", "completed_at")
    list_filter = ("completed_at",)
    search_fields = ("user__username", "test__title")


# =========================
# 📊 Writing Results (Teacher / AI)
# =========================
@admin.register(WritingResult)
class WritingResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "test",
        "status",
        "final_band",
        "submitted_at"
    )

    list_filter = ("status", "submitted_at")
    search_fields = ("user__username", "test__title")

    readonly_fields = ("submitted_at",)

    fieldsets = (

        ("Basic Info", {
            "fields": ("user", "test", "user_test", "status")
        }),

        ("Task 1 Scores", {
            "fields": (
                "task1_task",
                "task1_coherence",
                "task1_lexical",
                "task1_grammar",
                "task1_band",
            )
        }),

        ("Task 2 Scores", {
            "fields": (
                "task2_task",
                "task2_coherence",
                "task2_lexical",
                "task2_grammar",
                "task2_band",
            )
        }),

        ("Final", {
            "fields": ("final_band", "feedback")
        }),

        ("Time", {
            "fields": ("submitted_at",)
        }),
    )

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "is_active",
        "start_date",
        "end_date",
        "requests_used",
        "tokens_used",
        "days_left_display",
    )

    list_filter = (
        "plan",
        "is_active",
        "start_date",
        "end_date",
    )

    search_fields = (
        "user__username",
        "user__email",
    )

    readonly_fields = (
        "start_date",
        "last_reset",
    )

    ordering = ("-start_date",)

    # 🔥 custom column (days left)
    def days_left_display(self, obj):
        if obj.end_date:
            from django.utils import timezone
            days = (obj.end_date - timezone.now()).days
            return max(days, 0)
        return "∞"

    days_left_display.short_description = "Days Left"

from .models import HomePageContent

@admin.register(HomePageContent)
class HomePageContentAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active")

from django.contrib import admin
from .models import SpeakingTest, SpeakingQuestion, SpeakingAttempt


# 🔹 Inline questions inside test (VERY USEFUL)
class SpeakingQuestionInline(admin.TabularInline):
    model = SpeakingQuestion
    extra = 1
    fields = ("part", "question_text", "cue_points", "prep_time", "speak_time")
    show_change_link = True


# 🔹 Speaking Test Admin
@admin.register(SpeakingTest)
class SpeakingTestAdmin(admin.ModelAdmin):
    list_display = ("id", "title")
    search_fields = ("title",)
    inlines = [SpeakingQuestionInline]


# 🔹 Speaking Question Admin
@admin.register(SpeakingQuestion)
class SpeakingQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "test", "part", "short_question")
    list_filter = ("part", "test")
    search_fields = ("question_text",)

    fieldsets = (
        ("Basic Info", {
            "fields": ("test", "part", "question_text")
        }),
        ("Part 2 (Cue Card Only)", {
            "fields": ("cue_points", "prep_time", "speak_time"),
            "classes": ("collapse",),  # collapsible in admin
        }),
    )

    def short_question(self, obj):
        return obj.question_text[:50]
    short_question.short_description = "Question"


# 🔹 Speaking Attempt Admin
@admin.register(SpeakingAttempt)
class SpeakingAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "test",
        "overall_band",
        "created_at"
    )

    list_filter = ("created_at", "test")
    search_fields = ("user__username", "transcript")

    readonly_fields = (
        "transcript",
        "fluency_score",
        "grammar_score",
        "vocabulary_score",
        "pronunciation_score",
        "overall_band",
        "feedback",
        "created_at",
    )

    fieldsets = (
        ("User Info", {
            "fields": ("user", "question", "audio")
        }),
        ("AI Results", {
            "fields": (
                "transcript",
                "fluency_score",
                "grammar_score",
                "vocabulary_score",
                "pronunciation_score",
                "overall_band",
                "feedback",
            )
        }),
        ("Metadata", {
            "fields": ("created_at",)
        }),
    )