from django.db import models
from django.contrib.auth.models import User


# =========================
# 📘 READING TEST
# =========================
class ReadingTest(models.Model):
    title = models.CharField(max_length=255)
    duration_minutes = models.PositiveIntegerField(default=60)
    start_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


# =========================
# 📄 PASSAGE
# =========================
class Passage(models.Model):
    test = models.ForeignKey(
        ReadingTest,
        on_delete=models.CASCADE,
        related_name="passages"
    )

    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, null=True, blank=True)
    content = models.TextField(null=True, blank=True)
    order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.test.title} - Passage {self.order}"

class Paragraph(models.Model):
    passage = models.ForeignKey(
        Passage,
        on_delete=models.CASCADE,
        related_name="paragraphs"
    )

    label = models.CharField(max_length=2)  # A, B, C
    content = models.TextField()
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.label}"


# =========================
# 📦 QUESTION GROUP
# =========================
class QuestionGroup(models.Model):
    GROUP_TYPES = [
        ("TFNG", "True False Not Given"),
        ("YESNO", "Yes No Not Given"),
        ("MCQ_SINGLE", "Multiple Choice (Single)"),
        ("MCQ_MULTI", "Multiple Choice (Multiple)"),
        ("MATCH_HEADING", "Matching Headings"),
        ("MATCH_INFO", "Matching Information"),
        ("MATCH_FEATURE", "Matching Features"),
        ("MATCH_ENDING", "Matching Sentence Endings"),
        ("SUMMARY_BANK", "Summary With Word Bank"),
        ("SUMMARY_NO_BANK", "Summary Without Word Bank"),
        ("SENTENCE", "Sentence Completion"),
        ("NOTE", "Note Completion"),
        ("FORM", "Form Completion"),
        ("DIAGRAM", "Diagram Completion"),
        ("TABLE", "Table Completion"),
        ("FLOW", "Flowchart Completion"),
        ("SHORT", "Short Answer"),
        ("LIST", "List Selection"),
    ]

    passage = models.ForeignKey(
        Passage,
        on_delete=models.CASCADE,
        related_name="groups"
    )

    title = models.CharField(max_length=255)
    instruction = models.TextField()
    group_type = models.CharField(max_length=50, choices=GROUP_TYPES)
    order = models.PositiveIntegerField()

    diagram_image = models.ImageField(
        upload_to="reading/diagrams/",
        null=True,
        blank=True
    )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.title} ({self.group_type})"


# =========================
# ❓ QUESTION
# =========================
class Question(models.Model):
    group = models.ForeignKey(
        QuestionGroup,
        on_delete=models.CASCADE,
        related_name="questions"
    )

    number = models.PositiveIntegerField()
    text = models.TextField(blank=True)
    correct_answer = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"Q{self.number}"


# =========================
# 🔘 OPTION (MCQ / MATCHING)
# =========================
class Option(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="options",
        null=True,
        blank=True
    )

    group = models.ForeignKey(
        QuestionGroup,
        on_delete=models.CASCADE,
        related_name="group_options",
        null=True,
        blank=True
    )

    label = models.CharField(max_length=10)  # A, B, C, i, ii
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.label}. {self.text}"


# =========================
# 🧠 USER TEST ATTEMPT (SUMMARY)
# =========================
class UserReadingTest(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reading_tests"
    )

    test = models.ForeignKey(
        ReadingTest,
        on_delete=models.CASCADE,
        related_name="user_attempts"
    )

    score = models.IntegerField(default=0)

    answers_json = models.JSONField(blank=True, null=True)

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.test.title}"


# =========================
# ✍️ USER ANSWER (CORE ENGINE)
# =========================
class UserAnswer(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    user_test = models.ForeignKey(
        UserReadingTest,
        on_delete=models.CASCADE,
        related_name="answers"
    )

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="user_answers"
    )

    test = models.ForeignKey(
        ReadingTest,
        on_delete=models.CASCADE
    )

    answer = models.TextField()

    is_correct = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user_test", "question")

    def __str__(self):
        return f"{self.user.username} - Q{self.question.number}"