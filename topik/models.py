
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.db.models import Sum
from django.utils import timezone

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ActiveQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class TopikExam(TimeStampedModel):
    class Level(models.TextChoices):
        TOPIK_I = "TOPIK_I", "TOPIK I"
        TOPIK_II = "TOPIK_II", "TOPIK II"

    class ExamType(models.TextChoices):
        REAL = "real", "Real Test"
        MOCK = "mock", "Mock Test"
        PRACTICE = "practice", "Practice Test"

    class ExamMode(models.TextChoices):
        FULL = "full", "Full Mock"
        READING_ONLY = "reading_only", "Reading Only"
        LISTENING_ONLY = "listening_only", "Listening Only"
        WRITING_ONLY = "writing_only", "Writing Only"
        SPEAKING_ONLY = "speaking_only", "Speaking Only"

    exam_mode = models.CharField(
        max_length=20,
        choices=ExamMode.choices,
        default=ExamMode.FULL
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.TOPIK_I)
    exam_type = models.CharField(max_length=20, choices=ExamType.choices, default=ExamType.PRACTICE)
    exam_number = models.PositiveIntegerField(blank=True, null=True, help_text="e.g. 91")
    paper_variant = models.CharField(max_length=20, blank=True, help_text="e.g. A, B")
    title_ko = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    total_questions = models.PositiveIntegerField(default=0)
    duration_minutes = models.PositiveIntegerField(default=100)  # full exam total
    is_active = models.BooleanField(default=True)

    objects = ActiveQuerySet.as_manager()

    class Meta:
        ordering = ["-exam_number", "title"]

    def __str__(self):
        extra = f" {self.paper_variant}" if self.paper_variant else ""
        return f"{self.get_level_display()} {self.exam_number or ''}{extra} - {self.title}".strip()

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f"{self.level}-{self.exam_number or self.title}-{self.paper_variant}".strip("-"))
            slug = base
            counter = 1
            while TopikExam.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_total_section_duration_minutes(self):
        return self.sections.filter(is_active=True).aggregate(
            total=Sum("duration_minutes")
        )["total"] or 0


class ExamSection(TimeStampedModel):
    class SectionType(models.TextChoices):
        LISTENING = "listening", "Listening"
        READING = "reading", "Reading"
        WRITING = "writing", "Writing"

    exam = models.ForeignKey(TopikExam, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=20, choices=SectionType.choices)
    title = models.CharField(max_length=100, blank=True)
    order = models.PositiveIntegerField(default=1)
    total_questions = models.PositiveIntegerField(default=0)
    duration_minutes = models.PositiveIntegerField(default=0)
    instruction = models.TextField(blank=True)
    audio_file = models.FileField(upload_to="topik/sections/audio/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    class Meta:
        ordering = ["exam", "order"]
        unique_together = ("exam", "name")

    def __str__(self):
        return f"{self.exam} - {self.get_name_display()}"


class ExamMaterial(TimeStampedModel):
    """
    Shared content block for listening or reading.
    One material can be used by one or more questions.
    Examples:
    - listening audio with 1 image question
    - reading notice/image with 1 question
    - reading message/article with questions 63-64
    """

    class MaterialType(models.TextChoices):
        AUDIO_ONLY = "audio_only", "Audio Only"
        AUDIO_IMAGE = "audio_image", "Audio + Image"
        TEXT_ONLY = "text_only", "Text Only"
        TEXT_IMAGE = "text_image", "Text + Image"
        IMAGE_ONLY = "image_only", "Image Only"
        MIXED = "mixed", "Mixed"

    class DisplayType(models.TextChoices):
        SINGLE = "single", "Single Question Material"
        GROUP = "group", "Grouped Questions Material"

    section = models.ForeignKey(ExamSection, on_delete=models.CASCADE, related_name="materials")
    title = models.CharField(max_length=255, blank=True)
    instruction = models.TextField(blank=True)
    material_type = models.CharField(max_length=20, choices=MaterialType.choices)
    display_type = models.CharField(max_length=20, choices=DisplayType.choices, default=DisplayType.SINGLE)

    start_number = models.PositiveIntegerField(blank=True, null=True)
    end_number = models.PositiveIntegerField(blank=True, null=True)

    content_text = models.TextField(blank=True)
    image = models.ImageField(upload_to="topik/materials/images/", blank=True, null=True)

    order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["section", "order", "id"]
        unique_together = ("section", "order")

    def __str__(self):
        label = self.title or f"Material {self.order}"
        return f"{self.section} - {label}"

    def clean(self):
        super().clean()

        if self.start_number and self.end_number and self.start_number > self.end_number:
            raise ValidationError("start_number cannot be greater than end_number.")

        if not self.content_text and not self.image:
            raise ValidationError("Material must have at least one of content_text or image.")

class ExamQuestion(TimeStampedModel):
    class QuestionType(models.TextChoices):
        MCQ_SINGLE = "mcq_single", "Multiple Choice - Single Answer"
        TRUE_FALSE = "true_false", "True / False"
        MATCHING = "matching", "Matching"
        ORDERING = "ordering", "Ordering"
        SHORT_ANSWER = "short_answer", "Short Answer"

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    material = models.ForeignKey(ExamMaterial, on_delete=models.CASCADE, related_name="questions")
    question_number = models.PositiveIntegerField()
    question_text = models.TextField(blank=True, null=True)
    question_type = models.CharField(max_length=30, choices=QuestionType.choices, default=QuestionType.MCQ_SINGLE)

    image = models.ImageField(upload_to="topik/questions/images/", blank=True, null=True)

    score = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=1)
    difficulty = models.CharField(max_length=20, choices=Difficulty.choices, blank=True)
    explanation = models.TextField(blank=True)
    correct_text_answer = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["question_number", "order", "id"]
        unique_together = (
            ("material", "question_number"),
            ("material", "order"),
        )

    def __str__(self):
        return f"Q{self.question_number} - {self.material.section.exam}"

    @property
    def exam(self):
        return self.material.section.exam

    @property
    def section(self):
        return self.material.section

    def clean(self):
        super().clean()

        if self.question_type == self.QuestionType.SHORT_ANSWER and not self.correct_text_answer:
            raise ValidationError({"correct_text_answer": "This field is required for short answer questions."})


class QuestionChoice(TimeStampedModel):
    question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE, related_name="choices")
    label = models.CharField(max_length=10, blank=True, help_text="A, B, C, D or ① ② ③ ④")
    choice_text = models.CharField(max_length=500, blank=True)
    image = models.ImageField(upload_to="topik/choices/images/", blank=True, null=True)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["question", "order", "id"]
        unique_together = (
            ("question", "order"),
            ("question", "label"),
        )

    def __str__(self):
        return f"{self.question} - {self.label or self.order}"

    def clean(self):
        super().clean()
        if not self.choice_text and not self.image:
            raise ValidationError("Choice must have either choice_text or image.")


class ExamAttempt(TimeStampedModel):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In Progress"
        SUBMITTED = "submitted", "Submitted"
        EXPIRED = "expired", "Expired"
        EVALUATED = "EVALUATED", "Evaluated"

    current_section = models.ForeignKey(
        "ExamSection",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="current_attempts",
    )
    current_section_started_at = models.DateTimeField(null=True, blank=True)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="topik_attempts")
    exam = models.ForeignKey(TopikExam, on_delete=models.CASCADE, related_name="attempts")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)

    started_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(blank=True, null=True)

    total_score = models.PositiveIntegerField(default=0)
    listening_score = models.PositiveIntegerField(default=0)
    reading_score = models.PositiveIntegerField(default=0)
    writing_score = models.PositiveIntegerField(default=0)
    tab_switch_count = models.PositiveIntegerField(default=0)
    fullscreen_exit_count = models.PositiveIntegerField(default=0)
    copy_attempt_count = models.PositiveIntegerField(default=0)
    paste_attempt_count = models.PositiveIntegerField(default=0)
    right_click_count = models.PositiveIntegerField(default=0)
    ai_evaluated = models.BooleanField(default=False)
    ai_feedback = models.TextField(blank=True)
    ai_evaluated_at = models.DateTimeField(null=True, blank=True)
    is_flagged = models.BooleanField(default=False)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user} - {self.exam} - {self.status}"

    def get_remaining_seconds(self):
        if self.status != self.Status.IN_PROGRESS:
            return 0

        duration = self.exam.duration_minutes * 60
        elapsed = int((timezone.now() - self.started_at).total_seconds())
        remaining = duration - elapsed
        return max(0, remaining)

    def get_current_section_remaining_seconds(self):
        if (
            self.status != self.Status.IN_PROGRESS
            or not self.current_section
            or not self.current_section_started_at
        ):
            return 0

        duration = self.current_section.duration_minutes * 60
        elapsed = int((timezone.now() - self.current_section_started_at).total_seconds())
        remaining = duration - elapsed
        return max(0, remaining)

    def move_to_next_section(self):
        if not self.exam_id:
            return None

        sections = list(
            self.exam.sections.filter(is_active=True).order_by("order")
        )

        if not sections:
            return None

        if not self.current_section:
            self.current_section = sections[0]
            self.current_section_started_at = timezone.now()
            self.save(update_fields=["current_section", "current_section_started_at"])
            return self.current_section

        current_index = next(
            (i for i, s in enumerate(sections) if s.id == self.current_section_id),
            None
        )

        if current_index is None:
            self.current_section = sections[0]
            self.current_section_started_at = timezone.now()
            self.save(update_fields=["current_section", "current_section_started_at"])
            return self.current_section

        next_index = current_index + 1
        if next_index >= len(sections):
            return None

        self.current_section = sections[next_index]
        self.current_section_started_at = timezone.now()
        self.save(update_fields=["current_section", "current_section_started_at"])
        return self.current_section
class ExamAnswer(TimeStampedModel):
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE, related_name="answers")

    selected_choice = models.ForeignKey(
        QuestionChoice,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="selected_in_answers",
    )
    text_answer = models.CharField(max_length=255, blank=True)

    is_correct = models.BooleanField(default=False)
    score_awarded = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("attempt", "question")
        ordering = ["question__question_number"]

    def __str__(self):
        return f"{self.attempt} - Q{self.question.question_number}"

    def clean(self):
        super().clean()

        if self.selected_choice and self.selected_choice.question_id != self.question_id:
            raise ValidationError("Selected choice does not belong to this question.")

class ExamEventLog(TimeStampedModel):
    class EventType(models.TextChoices):
        TAB_SWITCH = "tab_switch", "Tab Switch"
        FULLSCREEN_EXIT = "fullscreen_exit", "Fullscreen Exit"
        COPY_ATTEMPT = "copy_attempt", "Copy Attempt"
        PASTE_ATTEMPT = "paste_attempt", "Paste Attempt"
        RIGHT_CLICK = "right_click", "Right Click"
        KEY_BLOCK = "key_block", "Blocked Shortcut"

    attempt = models.ForeignKey(
        ExamAttempt,
        on_delete=models.CASCADE,
        related_name="event_logs"
    )
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    details = models.TextField(blank=True)

    def __str__(self):
        return f"{self.attempt} - {self.event_type}"

class WritingTask(TimeStampedModel):
    class TaskType(models.TextChoices):
        GAP_FILL="gap_fill","Gap fill (51-52)"
        GRAPH_WRITING="graph_writing","Graph writing (53)"
        ESSAY="essay","Essay (54)"

    section=models.ForeignKey(
        ExamSection,on_delete=models.CASCADE,
        related_name="writing_tasks",
        limit_choices_to={"name":ExamSection.SectionType.WRITING}
    )
    task_number=models.PositiveIntegerField(help_text="Example: 51,52,53,54")
    task_type=models.CharField(max_length=30,choices=TaskType.choices)

    title=models.CharField(max_length=255,blank=True)
    instruction=models.TextField(blank=True)
    prompt=models.TextField(help_text="Main writing questions/prompt")

    image=models.ImageField(upload_to="topik/writing/tasks",blank=True,null=True)

    min_words=models.PositiveIntegerField(default=0,blank=True)
    max_words=models.PositiveIntegerField(default=0,blank=True)

    score=models.PositiveIntegerField(default=0)
    order=models.PositiveIntegerField(default=1)
    is_active=models.BooleanField(default=True)

    class Meta:
        ordering=["task_number","order"]
        unique_together=(
        ("section","task_number"),
        ("section","order")
        )

    def __str__(self):
        return f"Writing Task {self.task_number} - {self.section.exam}"

    def clean(self):
        super().clean()

        valid_numbers = {51, 52, 53, 54}
        if self.task_number not in valid_numbers:
            raise ValidationError({
                "task_number": "Writing task number must be one of 51, 52, 53, 54."
            })

        if self.section.name != ExamSection.SectionType.WRITING:
            raise ValidationError("WritingTask can only belong to a WRITING section.")

        if self.task_number in [51, 52] and self.task_type != self.TaskType.GAP_FILL:
            raise ValidationError({"task_type": "Tasks 51 and 52 must use GAP_FILL."})

        if self.task_number == 53 and self.task_type != self.TaskType.GRAPH_WRITING:
            raise ValidationError({"task_type": "Task 53 must use GRAPH_WRITING."})

        if self.task_number == 54 and self.task_type != self.TaskType.ESSAY:
            raise ValidationError({"task_type": "Task 54 must use ESSAY."})

        if self.task_number == 51:
            self.score = 10
        elif self.task_number == 52:
            self.score = 10
        elif self.task_number == 53:
            self.score = 30
        elif self.task_number == 54:
            self.score = 50

        if self.task_type in [self.TaskType.GRAPH_WRITING, self.TaskType.ESSAY] and not self.min_words:
            raise ValidationError({
                "min_words": "This field is required for long writing tasks."
            })

class WritingTaskBlank(TimeStampedModel):
    task=models.ForeignKey(
        WritingTask,
        on_delete=models.CASCADE,
        related_name="blanks",
        limit_choices_to={"task_type":WritingTask.TaskType.GAP_FILL},
    )
    blank_order=models.PositiveIntegerField(default=1)
    answer_label=models.CharField(max_length=20,blank=True,help_text="Example:Blank 1")
    correct_answer = models.CharField(max_length=250, blank=True, null=True)
    scoring_note = models.TextField(blank=True)

    class Meta:
        ordering=["blank_order"]
        unique_together=(
        ("task","blank_order")
        )
    def __str__(self):
        return f"{self.task}- Blank {self.blank_order}"

class WritingSubmission(TimeStampedModel):
    attempt = models.ForeignKey(
        ExamAttempt,
        on_delete=models.CASCADE,
        related_name="writing_submissions",
    )
    task = models.ForeignKey(
        WritingTask,
        on_delete=models.CASCADE,
        related_name="submissions",
    )

    answer_text = models.TextField(blank=True)
    word_count = models.PositiveIntegerField(default=0)

    is_correct = models.BooleanField(default=False)  # mostly useful for 51-52
    score_awarded = models.PositiveIntegerField(default=0)

    ai_score = models.FloatField(blank=True, null=True)
    ai_feedback = models.JSONField(blank=True, null=True)
    final_score = models.FloatField(blank=True, null=True)

    class Meta:
        ordering = ["task__task_number"]
        unique_together = (
            ("attempt", "task"),
        )

    def __str__(self):
        return f"{self.attempt} - Writing {self.task.task_number}"

    def clean(self):
        super().clean()

        if self.task.section.exam_id != self.attempt.exam_id:
            raise ValidationError("Task does not belong to the same exam as this attempt.")

    def save(self, *args, **kwargs):
        if self.answer_text:
            self.word_count = len(self.answer_text.split())
        else:
            self.word_count = 0
        super().save(*args, **kwargs)


class UserProgressInsight(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="topik_progress_insight",
    )
    summary = models.TextField(blank=True)
    focus_area = models.CharField(max_length=100, blank=True)
    advice_items = models.JSONField(default=list, blank=True)

    based_on_attempt_count = models.PositiveIntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} Progress Insight"



class SpeakingQuestion(models.Model):
    PART_CHOICES = [
        ("PART1", "Part 1"),
        ("PART2", "Part 2"),
        ("PART3", "Part 3"),
    ]

    TYPE_CHOICES = [
        ("SHORT", "Short Answer"),
        ("TOPIC", "Topic Card"),
        ("OPINION", "Opinion"),
        ("PICTURE", "Picture Description"),
        ("ROLEPLAY", "Role Play"),
    ]

    DIFFICULTY_CHOICES = [
        ("BEGINNER", "Beginner"),
        ("INTERMEDIATE", "Intermediate"),
        ("ADVANCED", "Advanced"),
    ]

    part = models.CharField(max_length=20, choices=PART_CHOICES)
    question_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default="BEGINNER"
    )

    title = models.CharField(max_length=255, blank=True)
    prompt = models.TextField()
    follow_up_questions = models.JSONField(default=list, blank=True)

    prep_time = models.PositiveIntegerField(default=30)
    speak_time = models.PositiveIntegerField(default=60)

    sample_answer = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)

    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["part", "order", "id"]

    def __str__(self):
        return self.title or self.prompt[:60]


class SpeakingTest(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.title


class SpeakingTestQuestion(models.Model):
    test = models.ForeignKey(
        "SpeakingTest",
        on_delete=models.CASCADE,
        related_name="test_questions"
    )
    question = models.ForeignKey(
        "SpeakingQuestion",
        on_delete=models.CASCADE,
        related_name="test_links"
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        unique_together = ("test", "question")

    def __str__(self):
        return f"{self.test.title} - {self.question.title or self.question.prompt[:30]}"


class SpeakingAttempt(models.Model):
    class Status:
        IN_PROGRESS = "IN_PROGRESS"
        SUBMITTED = "SUBMITTED"
        EVALUATED = "EVALUATED"

    STATUS_CHOICES = [
        (Status.IN_PROGRESS, "In Progress"),
        (Status.SUBMITTED, "Submitted"),
        (Status.EVALUATED, "Evaluated"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="speaking_attempts"
    )
    test = models.ForeignKey(
        "SpeakingTest",
        on_delete=models.CASCADE,
        related_name="attempts"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=Status.IN_PROGRESS
    )

    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)

    overall_score = models.FloatField(null=True, blank=True)
    ai_feedback = models.JSONField(default=dict, blank=True,null=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user} - {self.test.title}"

class SpeakingAnswer(models.Model):
    attempt = models.ForeignKey(
        "SpeakingAttempt",
        on_delete=models.CASCADE,
        related_name="answers"
    )
    question = models.ForeignKey(
        "SpeakingQuestion",
        on_delete=models.CASCADE,
        related_name="answers"
    )
    audio_file = models.FileField(
        upload_to="speaking_answers/",
        null=True,
        blank=True
    )

    transcript = models.TextField(blank=True)
    ai_score = models.FloatField(null=True, blank=True)
    ai_feedback = models.JSONField(default=dict, blank=True,null=True)

    grammar_score = models.FloatField(null=True, blank=True)
    fluency_score = models.FloatField(null=True, blank=True)
    vocabulary_score = models.FloatField(null=True, blank=True)
    pronunciation_score = models.FloatField(null=True, blank=True)
    task_completion_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        unique_together = ("attempt", "question")

    def __str__(self):
        return f"Answer - {self.question.title or self.question.prompt[:30]}"