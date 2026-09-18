# SmartCRM

Учебная CRM-система для малого бизнеса: клиенты, сделки, задачи и статистика.

## Возможности MVP

- авторизация пользователей;
- создание, изменение, удаление и поиск клиентов;
- сделки со статусами и суммами;
- задачи со сроками и приоритетами;
- панель с основными показателями.

## Технологии

Python 3.12, Django 5.2 LTS, SQLite и локальный CSS без внешних CDN.

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Откройте `http://127.0.0.1:8000/`. Подробности архитектуры находятся в
[`ARCHITECTURE.md`](ARCHITECTURE.md).

В Windows PowerShell после создания окружения активация не обязательна:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Войдите под созданным пользователем. Новые аккаунты можно создать в `/admin/`.
Публичная регистрация не реализована. Каждый аккаунт имеет отдельный набор данных.
Пароль при вводе в терминале не отображается — это нормально.

## Проверка

```bash
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
```

Это локальный учебный MVP, не готовая к публичному размещению система.
Не загружайте `.venv`, базу `db.sqlite3`, пароли или настоящие клиентские данные.
Инструкция по ограничениям и настройке публикации — в ARCHITECTURE.md.

## Командная работа

Новые задачи выполняются в ветках `feature/<название>` и объединяются с `main`
через Pull Request.
