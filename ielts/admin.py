from django.contrib import admin
from .models import *

# =========================================================
# 📘 READING ADMIN
# =========================================================

class ParagraphInline(admin.TabularInline):
    model = Paragraph
    extra = 1
    fields = ("label", "content", "order")
    ordering = ("order",)


class OptionInline(admin.TabularInline):
    model = Option
    extra = 2
    fields = ("label", "text", "is_correct")
    ordering = ("label",)
    fk_name = "question"


class GroupOptionInline(admin.TabularInline):
    model = Option
    extra = 2
    fields = ("label", "text")
    ordering = ("label",)
    fk_name = "group"


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 2
    fields = ("number", "text", "correct_answer")
    ordering = ("number",)


@admin.register(ReadingTest)
class ReadingTestAdmin(admin.ModelAdmin):
    list_display = ["title", "duration_minutes", "created_at"]


@admin.register(Passage)
class PassageAdmin(admin.ModelAdmin):
    list_display = ["title", "test", "order"]
    inlines = [ParagraphInline]


@admin.register(QuestionGroup)
class QuestionGroupAdmin(admin.ModelAdmin):
    list_display = ["title", "group_type", "passage", "order"]
    inlines = [QuestionInline, GroupOptionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["number", "group", "correct_answer"]
    inlines = [OptionInline]


@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ["label", "text", "question", "group"]


@admin.register(UserReadingTest)
class UserReadingTestAdmin(admin.ModelAdmin):
    list_display = ["user", "test", "score", "completed_at"]


@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ["user", "question", "is_correct"]


@admin.register(ReadingAIReport)
class ReadingAIReportAdmin(admin.ModelAdmin):
    list_display = ["user", "avg_score", "avg_accuracy", "updated_at"]


# =========================================================
# 🎧 LISTENING ADMIN
# =========================================================

class ListeningOptionInline(admin.TabularInline):
    model = ListeningOption
    extra = 2


class ListeningQuestionInline(admin.TabularInline):
    model = ListeningQuestion
    extra = 2


class ListeningGroupInline(admin.TabularInline):
    model = ListeningGroup
    extra = 1


class ListeningSectionInline(admin.TabularInline):
    model = ListeningSection
    extra = 1


@admin.register(ListeningTest)
class ListeningTestAdmin(admin.ModelAdmin):
    list_display = ["title", "created_at"]
    inlines = [ListeningSectionInline]


@admin.register(ListeningSection)
class ListeningSectionAdmin(admin.ModelAdmin):
    list_display = ["test", "title", "order"]
    inlines = [ListeningGroupInline]


@admin.register(ListeningGroup)
class ListeningGroupAdmin(admin.ModelAdmin):
    list_display = ["section", "group_type", "order"]
    inlines = [ListeningQuestionInline]


@admin.register(ListeningQuestion)
class ListeningQuestionAdmin(admin.ModelAdmin):
    list_display = ["number", "group"]
    inlines = [ListeningOptionInline]


@admin.register(UserListeningTest)
class UserListeningTestAdmin(admin.ModelAdmin):
    list_display = ["user", "test", "score", "completed_at"]


@admin.register(UserListeningAnswer)
class UserListeningAnswerAdmin(admin.ModelAdmin):
    list_display = ["user_test", "question", "is_correct"]


@admin.register(ListeningAIReport)
class ListeningAIReportAdmin(admin.ModelAdmin):
    list_display = ["user", "avg_score", "avg_accuracy", "updated_at"]


# =========================================================
# ✍️ WRITING ADMIN
# =========================================================

class WritingTask1Inline(admin.StackedInline):
    model = WritingTask1
    extra = 0


class WritingTask2Inline(admin.StackedInline):
    model = WritingTask2
    extra = 0


@admin.register(WritingTest)
class WritingTestAdmin(admin.ModelAdmin):
    list_display = ["title", "duration_minutes"]
    inlines = [WritingTask1Inline, WritingTask2Inline]


@admin.register(UserWritingTest)
class UserWritingTestAdmin(admin.ModelAdmin):
    list_display = ["user", "test", "completed_at"]


@admin.register(WritingResult)
class WritingResultAdmin(admin.ModelAdmin):
    list_display = ["user", "test", "final_band", "status"]


# =========================================================
# 🎤 SPEAKING ADMIN
# =========================================================

class SpeakingQuestionInline(admin.TabularInline):
    model = SpeakingQuestion
    extra = 1


@admin.register(SpeakingTest)
class SpeakingTestAdmin(admin.ModelAdmin):
    list_display = ["title"]
    inlines = [SpeakingQuestionInline]


@admin.register(SpeakingQuestion)
class SpeakingQuestionAdmin(admin.ModelAdmin):
    list_display = ["test", "part"]


@admin.register(SpeakingAttempt)
class SpeakingAttemptAdmin(admin.ModelAdmin):
    list_display = ["user", "test", "overall_band"]


# =========================================================
# 💳 SUBSCRIPTION ADMIN
# =========================================================

class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "is_active",
        "ai_used_today",
        "tests_used_today",
        "start_date",
        "end_date",
    )

admin.site.register(Subscription, SubscriptionAdmin)


# =========================================================
# 🏠 HOME PAGE
# =========================================================

@admin.register(HomePageContent)
class HomePageContentAdmin(admin.ModelAdmin):
    list_display = ["title", "is_active"]