"""Fill a local SmartCRM database with fictional demonstration data.

Usage:
    python manage.py seed_demo --username YOUR_USERNAME

The command is idempotent and never deletes existing user records.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from crm.models import Client, Deal, Task


CLIENTS = [
    ("company", "Astana Digital Lab", "Астана", "IT и разработка", "Алия Серикова", "aliya@example.com", "+7 700 000 00 01"),
    ("company", "Qazaq Logistics", "Алматы", "Логистика", "Ерлан Касымов", "erlan@example.com", "+7 700 000 00 02"),
    ("company", "Orda Retail", "Астана", "Розничная торговля", "Мадина Омарова", "madina@example.com", "+7 700 000 00 03"),
    ("company", "Nomad Education", "Шымкент", "Образование", "Данияр Нурланов", "daniyar@example.com", "+7 700 000 00 04"),
    ("company", "Steppe Finance", "Алматы", "Финансы", "Айгерим Садыкова", "aigerim@example.com", "+7 700 000 00 05"),
    ("company", "Green City Solutions", "Караганда", "Экология", "Руслан Ибраев", "ruslan@example.com", "+7 700 000 00 06"),
    ("person", "Александр Иванов", "Астана", "", "", "alex@example.com", "+7 700 000 00 07"),
    ("person", "Айдана Бекова", "Алматы", "", "", "aidana@example.com", "+7 700 000 00 08"),
    ("person", "Нурбек Жумабаев", "Костанай", "", "", "nurbek@example.com", "+7 700 000 00 09"),
    ("person", "Диана Ахметова", "Астана", "", "", "diana@example.com", "+7 700 000 00 10"),
]

DEALS = [
    (0, "Внедрение CRM для отдела продаж", "in_progress", 1850000, 21),
    (1, "Автоматизация логистики", "new", 2700000, 40),
    (2, "Аналитика клиентских заказов", "won", 920000, -15),
    (3, "Портал онлайн-обучения", "in_progress", 1400000, 30),
    (4, "Интеграция платёжной системы", "lost", 1250000, -8),
    (5, "Панель экологического мониторинга", "new", 3100000, 55),
    (6, "Личный кабинет клиента", "won", 420000, -30),
    (7, "Автоматизация заявок", "in_progress", 650000, 14),
    (8, "Настройка отчётности", "new", 380000, 18),
    (9, "Система уведомлений", "won", 590000, -20),
    (0, "Поддержка CRM на 12 месяцев", "in_progress", 760000, 60),
    (2, "Интеграция с каталогом товаров", "new", 870000, 35),
]

TASKS = [
    (0, "Подготовить требования к CRM", "high", -4, False),
    (0, "Согласовать структуру клиентских карточек", "medium", 2, False),
    (1, "Проверить интеграцию API логистики", "high", 1, False),
    (1, "Подготовить коммерческое предложение", "medium", 5, False),
    (2, "Провести встречу по аналитике продаж", "low", 8, False),
    (3, "Протестировать регистрацию пользователей", "high", 3, False),
    (3, "Согласовать дизайн личного кабинета", "medium", 11, False),
    (4, "Подготовить акт завершения", "low", -5, True),
    (5, "Оценить стоимость облачного хостинга", "medium", 7, False),
    (5, "Проверить резервное копирование", "high", 4, False),
    (6, "Собрать обратную связь от заказчика", "low", -7, True),
    (7, "Настроить уведомления о задачах", "medium", 6, False),
    (8, "Проверить фильтрацию отчётов", "high", 0, False),
    (9, "Согласовать финальную версию проекта", "medium", 12, False),
    (0, "Добавить тесты разграничения доступа", "high", 9, False),
    (2, "Проверить отображение сделок на дашборде", "medium", 15, False),
    (1, "Подготовить демонстрацию клиенту", "low", 17, False),
    (4, "Обновить техническую документацию", "medium", -2, True),
]


class Command(BaseCommand):
    help = "Create fictional clients, deals and tasks for a selected CRM user (without duplicates)."

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Existing CRM username; required when multiple users exist")

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        username = options["username"]
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist as exc:
                raise CommandError(f"User {username!r} does not exist. Create it first.") from exc
        else:
            users = User.objects.filter(is_active=True, is_superuser=True)
            if users.count() != 1:
                raise CommandError("Specify --username YOUR_USERNAME (or have exactly one active superuser).")
            user = users.get()

        if hasattr(user, "portal_profile"):
            raise CommandError("Select a CRM manager, not a portal client account.")

        today = timezone.localdate()
        clients = []
        counts = {"clients": 0, "deals": 0, "tasks": 0}

        for kind, name, city, industry, contact, email, phone in CLIENTS:
            client, created = Client.objects.get_or_create(
                owner=user, name=name,
                defaults={
                    "kind": kind, "city": city, "industry": industry,
                    "contact_person": contact, "email": email, "phone": phone,
                    "notes": "Демонстрационная запись для учебного проекта SmartCRM.",
                },
            )
            clients.append(client)
            counts["clients"] += int(created)

        for client_index, title, status, amount, days in DEALS:
            _, created = Deal.objects.get_or_create(
                owner=user, client=clients[client_index], title=title,
                defaults={
                    "status": status, "amount": Decimal(amount),
                    "expected_close_date": today + timedelta(days=days),
                },
            )
            counts["deals"] += int(created)

        for client_index, title, priority, days, completed in TASKS:
            _, created = Task.objects.get_or_create(
                owner=user, client=clients[client_index], title=title,
                defaults={
                    "description": "Учебная задача с демонстрационными данными.",
                    "priority": priority, "due_date": today + timedelta(days=days),
                    "is_completed": completed,
                },
            )
            counts["tasks"] += int(created)

        self.stdout.write(self.style.SUCCESS(
            f"Demo data for {user.username}: added {counts['clients']} clients, "
            f"{counts['deals']} deals, {counts['tasks']} tasks. "
            "Existing records were preserved."
        ))
