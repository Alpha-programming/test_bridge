from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError


# =========================================================
# 📘 READING MODELS
# =========================================================

class ReadingTest(models.Model):
    title = models.CharField(max_length=255)
    duration_minutes = models.PositiveIntegerField(default=60)
    start_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Passage(models.Model):
    test = models.ForeignKey(ReadingTest, on_delete=models.CASCADE, related_name="passages")
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
    passage = models.ForeignKey(Passage, on_delete=models.CASCADE, related_name="paragraphs")
    label = models.CharField(max_length=2, null=True, blank=True)
    content = models.TextField(null=True, blank=True)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.label}"


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

    passage = models.ForeignKey(Passage, on_delete=models.CASCADE, related_name="groups")
    title = models.CharField(max_length=255)
    instruction = models.TextField()
    group_type = models.CharField(max_length=50, choices=GROUP_TYPES)
    order = models.PositiveIntegerField()

    diagram_image = models.ImageField(upload_to="reading/diagrams/", null=True, blank=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.title} ({self.group_type})"


class Question(models.Model):
    group = models.ForeignKey(QuestionGroup, on_delete=models.CASCADE, related_name="questions")
    number = models.PositiveIntegerField()
    text = models.TextField(blank=True)
    correct_answer = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"Q{self.number}"


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options", null=True, blank=True)
    group = models.ForeignKey(QuestionGroup, on_delete=models.CASCADE, related_name="group_options", null=True, blank=True)

    label = models.CharField(max_length=10)
    text = models.CharField(max_length=255, null=True, blank=True)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.label}. {self.text}"


class UserReadingTest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reading_tests")
    test = models.ForeignKey(ReadingTest, on_delete=models.CASCADE, related_name="user_attempts")

    score = models.IntegerField(default=0)
    answers_json = models.JSONField(blank=True, null=True)

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    mistake_stats = models.TextField(blank=True, null=True)
    accuracy = models.FloatField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "test"],
                condition=models.Q(completed_at__isnull=True),
                name="unique_active_test_per_user"
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.test.title}"


class UserAnswer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    user_test = models.ForeignKey(UserReadingTest, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="user_answers")
    test = models.ForeignKey(ReadingTest, on_delete=models.CASCADE)

    answer = models.TextField()
    is_correct = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user_test", "question")

    def __str__(self):
        return f"{self.user.username} - Q{self.question.number}"


class ReadingAIReport(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="reading_ai")

    total_tests = models.IntegerField(default=0)
    avg_score = models.FloatField(default=0)
    avg_accuracy = models.FloatField(default=0)

    weak_types = models.JSONField(default=dict)
    ai_response = models.JSONField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)


# =========================================================
# 🎧 LISTENING MODELS
# =========================================================

class ListeningTest(models.Model):
    title = models.CharField(max_length=255)
    audio = models.FileField(upload_to="listening/audio/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class ListeningSection(models.Model):
    test = models.ForeignKey(ListeningTest, on_delete=models.CASCADE, related_name="sections")
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]


class ListeningGroup(models.Model):
    GROUP_TYPES = [
        ("FORM", "Form Completion"),
        ("NOTE", "Note Completion"),
        ("MCQ", "Multiple Choice"),
        ("MAP", "Map Labeling"),
        ("MATCH", "Matching"),
    ]

    section = models.ForeignKey(ListeningSection, on_delete=models.CASCADE, related_name="groups")
    instruction = models.TextField()
    group_type = models.CharField(max_length=50, choices=GROUP_TYPES)
    order = models.PositiveIntegerField()

    image = models.ImageField(upload_to="listening/diagrams/", null=True, blank=True)

    class Meta:
        ordering = ["order"]


class ListeningQuestion(models.Model):
    group = models.ForeignKey(ListeningGroup, on_delete=models.CASCADE, related_name="questions")
    number = models.PositiveIntegerField()
    text = models.TextField(blank=True)
    correct_answer = models.TextField()

    class Meta:
        ordering = ["number"]


class ListeningOption(models.Model):
    question = models.ForeignKey(ListeningQuestion, on_delete=models.CASCADE, related_name="options")
    label = models.CharField(max_length=5)
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)


class UserListeningTest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    test = models.ForeignKey(ListeningTest, on_delete=models.CASCADE)

    score = models.IntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    mistake_stats = models.TextField(blank=True, null=True)
    accuracy = models.FloatField(default=0)

    class Meta:
        unique_together = ("user", "test")


class UserListeningAnswer(models.Model):
    user_test = models.ForeignKey(UserListeningTest, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(ListeningQuestion, on_delete=models.CASCADE)

    answer = models.TextField()
    is_correct = models.BooleanField(default=False)

    class Meta:
        unique_together = ("user_test", "question")


class ListeningAIReport(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="listening_ai")

    total_tests = models.IntegerField(default=0)
    avg_score = models.FloatField(default=0)
    avg_accuracy = models.FloatField(default=0)

    weak_types = models.JSONField(default=dict)
    ai_response = models.JSONField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} Listening AI"


# =========================================================
# ✍️ WRITING MODELS
# =========================================================

class WritingTest(models.Model):
    title = models.CharField(max_length=255)
    duration_minutes = models.PositiveIntegerField(default=60)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class WritingTask1(models.Model):
    test = models.OneToOneField(WritingTest, on_delete=models.CASCADE, related_name="task1")
    instruction = models.TextField()
    image = models.ImageField(upload_to="writing/task1/", null=True, blank=True)

    def __str__(self):
        return f"{self.test.title} - Task 1"


class WritingTask2(models.Model):
    test = models.OneToOneField(WritingTest, on_delete=models.CASCADE, related_name="task2")
    question = models.TextField()

    def __str__(self):
        return f"{self.test.title} - Task 2"


class UserWritingTest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    test = models.ForeignKey(WritingTest, on_delete=models.CASCADE)

    task1_answer = models.TextField(blank=True)
    task2_answer = models.TextField(blank=True)

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "test")


class WritingResult(models.Model):
    STATUS_CHOICES = (
        ("submitted", "Submitted"),
        ("checked", "Checked"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    test = models.ForeignKey(WritingTest, on_delete=models.CASCADE, related_name="results")
    user_test = models.OneToOneField(UserWritingTest, on_delete=models.CASCADE, related_name="result")

    submitted_at = models.DateTimeField(auto_now_add=True)

    task1_task = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    task1_coherence = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    task1_lexical = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    task1_grammar = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)

    task2_task = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    task2_coherence = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    task2_lexical = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    task2_grammar = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)

    task1_band = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    task2_band = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    final_band = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)

    feedback = models.TextField(null=True, blank=True)
    advanced = models.TextField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="submitted")

    def __str__(self):
        return f"{self.user.username} - {self.test.title}"


# =========================================================
# 🎤 SPEAKING MODELS
# =========================================================

class SpeakingTest(models.Model):
    title = models.CharField(max_length=255)
    duration_minutes = models.PositiveIntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)


class SpeakingQuestion(models.Model):
    PART_CHOICES = (
        (1, 'Part 1'),
        (2, 'Part 2'),
        (3, 'Part 3'),
    )

    test = models.ForeignKey(SpeakingTest, on_delete=models.CASCADE, related_name="questions")
    part = models.IntegerField(choices=PART_CHOICES)
    question_text = models.TextField()

    cue_points = models.TextField(blank=True, null=True)
    prep_time = models.IntegerField(blank=True, null=True)
    speak_time = models.IntegerField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.part == 2 and not self.cue_points:
            raise ValidationError("Part 2 must have cue points")

    def save(self, *args, **kwargs):
        if self.part == 2:
            if not self.prep_time:
                self.prep_time = 60
            if not self.speak_time:
                self.speak_time = 120
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Part {self.part}: {self.question_text[:50]}"


class UserSpeakingTest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    test = models.ForeignKey(SpeakingTest, on_delete=models.CASCADE)

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class SpeakingAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    test = models.ForeignKey(SpeakingTest, on_delete=models.CASCADE)
    question = models.ForeignKey(SpeakingQuestion, on_delete=models.CASCADE)

    audio = models.FileField(upload_to='speaking/')
    transcript = models.TextField(blank=True)

    fluency_score = models.FloatField(null=True, blank=True)
    grammar_score = models.FloatField(null=True, blank=True)
    vocabulary_score = models.FloatField(null=True, blank=True)
    pronunciation_score = models.FloatField(null=True, blank=True)
    overall_band = models.FloatField(null=True, blank=True)

    feedback = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)


# =========================================================
# 💳 SUBSCRIPTION MODEL
# =========================================================

class Subscription(models.Model):
    PLAN_CHOICES = [
        ("FREE", "Free"),
        ("STANDARD", "Standard"),
        ("PRO", "Pro"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="FREE")

    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    ai_used_today = models.IntegerField(default=0)
    tests_used_today = models.IntegerField(default=0)

    last_reset = models.DateField(auto_now_add=True)

    def is_expired(self):
        if self.plan == "FREE":
            return False
        return self.end_date and timezone.now() > self.end_date

    def reset_daily_usage(self):
        today = timezone.now().date()

        if self.last_reset != today:
            self.ai_used_today = 0
            self.tests_used_today = 0
            self.last_reset = today
            self.save()

    def get_limits(self):
        return {
            "FREE": {"ai": 1, "tests": 2},
            "STANDARD": {"ai": 5, "tests": 10},
            "PRO": {"ai": 100, "tests": 100},
        }.get(self.plan, {"ai": 0, "tests": 0})

    def __str__(self):
        return f"{self.user.username} - {self.plan}"


# =========================================================
# 🏠 HOME PAGE
# =========================================================

class HomePageContent(models.Model):
    title = models.CharField(max_length=255, default="Boost your IELTS score 🚀")
    subtitle = models.TextField(blank=True)
    image = models.ImageField(upload_to="home/", null=True, blank=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return "Homepage Content"