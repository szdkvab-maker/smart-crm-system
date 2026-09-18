from django.contrib.auth.models import User
from django.db import models


class Client(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="clients")
    name = models.CharField("Имя или компания", max_length=150)
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Телефон", max_length=30, blank=True)
    company = models.CharField("Компания", max_length=150, blank=True)
    notes = models.TextField("Заметки", blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"

    def __str__(self):
        return self.name


class Deal(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Новая"
        IN_PROGRESS = "in_progress", "В работе"
        WON = "won", "Успешно"
        LOST = "lost", "Проиграна"

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="deals")
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="deals")
    title = models.CharField("Название", max_length=180)
    amount = models.DecimalField("Сумма", max_digits=12, decimal_places=2, default=0)
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.NEW)
    expected_close_date = models.DateField("Плановая дата закрытия", blank=True, null=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Сделка"
        verbose_name_plural = "Сделки"

    def __str__(self):
        return self.title


class Task(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Низкий"
        MEDIUM = "medium", "Средний"
        HIGH = "high", "Высокий"

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tasks")
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, related_name="tasks", null=True, blank=True)
    title = models.CharField("Название", max_length=180)
    description = models.TextField("Описание", blank=True)
    due_date = models.DateField("Срок", blank=True, null=True)
    priority = models.CharField("Приоритет", max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    is_completed = models.BooleanField("Выполнено", default=False)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        ordering = ["is_completed", "due_date", "-created_at"]
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"

    def __str__(self):
        return self.title
