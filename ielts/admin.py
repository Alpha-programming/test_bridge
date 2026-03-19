from django.contrib import admin
from .models import (
    ReadingTest,
    Passage,
    Paragraph,
    QuestionGroup,
    Question,
    Option,
)


# =========================
# 🔹 PARAGRAPH INLINE (A, B, C)
# =========================
class ParagraphInline(admin.TabularInline):
    model = Paragraph
    extra = 1
    fields = ("label", "content", "order")
    ordering = ("order",)


# =========================
# 🔹 OPTION INLINE (MCQ)
# =========================
class OptionInline(admin.TabularInline):
    model = Option
    extra = 2
    fields = ("label", "text", "is_correct")
    ordering = ("label",)


# =========================
# 🔹 QUESTION ADMIN
# =========================
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["number", "group", "get_passage"]
    ordering = ["number"]
    search_fields = ["text"]
    list_filter = ["group__group_type"]

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
# 🔹 GROUP OPTIONS INLINE
# =========================
class GroupOptionInline(admin.TabularInline):
    model = Option
    fk_name = "group"
    extra = 2
    fields = ("label", "text")
    ordering = ("label",)


# =========================
# 🔹 QUESTION GROUP ADMIN
# =========================
class QuestionGroupAdmin(admin.ModelAdmin):
    list_display = ["title", "group_type", "passage", "order"]
    list_filter = ["group_type", "passage"]
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
# 🔹 PASSAGE ADMIN (IMPORTANT)
# =========================
class PassageAdmin(admin.ModelAdmin):
    list_display = ["title","subtitle","test", "order"]
    list_filter = ["test"]
    search_fields = ["title", "content"]
    ordering = ["order"]

    save_on_top = True

    fieldsets = (
        ("Basic Info", {
            "fields": ("test","title","subtitle","order")
        }),
        ("Content (Optional)", {
            "fields": ("content",),
            "classes": ("collapse",)  # hide if using paragraphs
        }),
    )

    inlines = [ParagraphInline]  # 🔥 KEY FEATURE


# =========================
# 🔹 READING TEST ADMIN
# =========================
class ReadingTestAdmin(admin.ModelAdmin):
    list_display = ["title", "duration_minutes", "created_at"]
    search_fields = ["title"]
    ordering = ["-created_at"]
    save_on_top = True


# =========================
# 🔹 REGISTER
# =========================
admin.site.register(ReadingTest, ReadingTestAdmin)
admin.site.register(Passage, PassageAdmin)
admin.site.register(QuestionGroup, QuestionGroupAdmin)
admin.site.register(Question, QuestionAdmin)
admin.site.register(Option)
admin.site.register(Paragraph)