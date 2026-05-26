# News Platform

A full-stack Django news application supporting independent journalists,
publishers, editors, and reader subscriptions. Features include
role-based access control, an editor approval workflow that emails
subscribers and posts to X (Twitter) via Django signals, a RESTful
API with JWT authentication, and comprehensive automated tests.

Built as the capstone project for HyperionDev's AI Engineering
Level 2 course.

---

## Features

- **Three user roles** — Reader, Journalist, Editor — each with
  distinct permissions enforced through Django Groups.
- **Reader subscriptions** to publishers and independent journalists.
- **Article workflow** — journalists submit, editors review and
  approve, approved articles fan out to subscribers via email and
  X (Twitter) using a `post_save` signal.
- **Curated newsletters** — journalists assemble approved articles
  into themed collections.
- **RESTful API** with six article endpoints, JWT authentication,
  and role-based permission classes for third-party clients.
- **MariaDB** backend.
- **25+ automated unit tests** covering authentication, role
  authorisation, subscription filtering, and signal behaviour
  (with mocking for external services).

---

## Tech stack

| Layer            | Tool                                          |
|------------------|-----------------------------------------------|
| Backend          | Django 5.x                                    |
| API              | Django REST Framework + djangorestframework-simplejwt (JWT) |
| Database         | MariaDB (via `mysqlclient`)                   |
| Frontend         | Django templates + Bootstrap 5                |
| External APIs    | Tweepy (X / Twitter API v2)                   |
| Config           | python-dotenv                                 |
| Testing          | Django `APITestCase`, `unittest.mock`         |

---

### Role permission matrix

| Action                          | Reader | Journalist | Editor |
|---------------------------------|:------:|:----------:|:------:|
| View approved articles          |   ✓    |     ✓      |   ✓    |
| View own draft articles         |        |     ✓      |   ✓    |
| View all draft articles         |        |            |   ✓    |
| Create article                  |        |     ✓      |   ✓     |
| Edit own article (drafts too)   |        |     ✓      |   ✓    |
| Edit any article                |        |            |   ✓    |
| Delete own article (drafts too) |        |     ✓      |   ✓    |
| Delete any article              |        |            |   ✓    |
| Approve article                 |        |            |   ✓    |
| View publishers                 |   ✓    |     ✓      |   ✓    |
| Create / edit / delete publisher|        |            |   ✓    |
| Subscribe to publisher          |   ✓    |            |        |
| Subscribe to journalist         |   ✓    |            |        |
| Editor-created article auto-approved |   |            |   ✓    |

---

## Setup

### Prerequisites

- Python 3.11+
- MariaDB 10.6+ (or MySQL 8) running locally on port 3306
- A MariaDB user with database creation privileges (for the test DB)

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/ConorRyanBlake/django-news-capstone
cd django-news-capstone
python -m venv venv

# Windows
.\venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in the values:
- `SECRET_KEY` — generate one with
  `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- `DB_PASSWORD` — the password for your MariaDB user
- X / Twitter keys (optional — without them, the X integration
  skips gracefully with a log line)

### 4. Create the database

In the MariaDB shell:

```sql
CREATE DATABASE news_platform_db
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'news_user'@'localhost' IDENTIFIED BY 'YOUR_PASSWORD';
GRANT ALL PRIVILEGES ON *.* TO 'news_user'@'localhost';
FLUSH PRIVILEGES;
```

The `*.*` grant is required so Django can create and drop the
test database during `manage.py test`. For production, tighten
this back to `news_platform_db.*`.

### 5. Apply migrations and create a superuser

```bash
python manage.py migrate
python manage.py createsuperuser
```

When prompted, the superuser will be created without a role. After
logging into `/admin/`, edit the user and set their role to **Editor**
so they can access the editor dashboard.

### 6. Run the development server

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`.

---

## Usage

### Web interface

- `/` — home page with latest approved articles
- `/articles/` — full article listing (readers see subscribed content)
- `/newsletters/` — newsletter listing
- `/publishers/` — publisher listing (editors can create / edit / delete)
- `/journalist/` — journalist's dashboard with own drafts and published articles
- `/editor/` — pending-articles dashboard (editor only)
- `/accounts/login/`, `/register/` — auth
- `/admin/` — Django admin

### REST API

Base URL: `http://127.0.0.1:8000/api/`

#### Authentication

Obtain a JWT:

```bash
curl -X POST http://127.0.0.1:8000/api/token/ \
    -H "Content-Type: application/json" \
    -d '{"username": "your_username", "password": "your_password"}'
```

Response:

```json
{"refresh": "...", "access": "..."}
```

Include the access token in subsequent requests:

```bash
curl http://127.0.0.1:8000/api/articles/ \
    -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE"
```

Refresh an expired access token:

```bash
curl -X POST http://127.0.0.1:8000/api/token/refresh/ \
    -H "Content-Type: application/json" \
    -d '{"refresh": "YOUR_REFRESH_TOKEN_HERE"}'
```

#### Endpoints

| Method | Path                              | Role         | Purpose                                 |
|--------|-----------------------------------|--------------|-----------------------------------------|
| GET    | `/api/articles/`                  | Any auth     | List approved articles                  |
| GET    | `/api/articles/subscribed/`       | Reader       | List articles from subscriptions        |
| GET    | `/api/articles/<id>/`             | Any auth     | Retrieve one article                    |
| POST   | `/api/articles/`                  | Journalist   | Create article (author auto-assigned)   |
| PUT    | `/api/articles/<id>/`             | Author/Editor| Update article                          |
| DELETE | `/api/articles/<id>/`             | Author/Editor| Delete article                          |
| POST   | `/api/articles/<id>/approve/`     | Editor       | Approve article (triggers email + X)    |
| GET    | `/api/newsletters/`               | Any auth     | List newsletters                        |
| POST   | `/api/newsletters/`               | Journalist   | Create newsletter                       |
| PUT    | `/api/newsletters/<id>/`          | Author/Editor| Update newsletter                       |
| DELETE | `/api/newsletters/<id>/`          | Author/Editor| Delete newsletter                       |
| GET    | `/api/publishers/`                | Any auth     | List publishers                         |


---

## Approval workflow

When an editor approves an article, a `post_save` signal handler
(`news/signals.py`) fires and:

1. Emails all subscribers of the article's publisher AND of the
   article's journalist (deduplicated).
2. Posts a tweet to X with the article title and a link.

The signal is wired up so it only fires on the **transition** from
unapproved to approved — not on every subsequent save of an
already-approved article. This means editing typos doesn't re-spam
subscribers.

Both side-effects (`email_subscribers_of_article`, `post_to_x`) live
in `news/services.py` and fail silently if credentials are missing
or the external service is unreachable, so the approval workflow
itself never crashes.

---

## Running the tests

```bash
python manage.py test news
```

The test suite covers:

- JWT authentication (token issuing, bad credentials, anonymous
  rejection)
- Role-based article visibility (reader / journalist / editor)
- Reader subscription filtering via `/api/articles/subscribed/`
- Journalist article creation (and that other roles are forbidden)
- Editor approve and delete actions
- Newsletter behaviour
- Signal logic with mocked email + X services

Run verbose for a per-test breakdown:

```bash
python manage.py test news --verbosity=2
```

---

## Project structure

```
news_project/
├── manage.py
├── requirements.txt
├── .env.example
├── README.md
├── diagrams/
│   ├── use_case_diagram.png
│   ├── class_diagram.png
│   ├── sequence_diagram_crud.png
│   └── sequence_diagram_approval.png
├── screenshots/
│   └── ...
├── news_project/
│   ├── settings.py
│   ├── urls.py
│   └── ...
└── news/
    ├── models.py          # CustomUser, Publisher, Article, Newsletter
    ├── views.py           # Web (template) views
    ├── api_views.py       # DRF viewsets
    ├── serializers.py     # DRF serializers
    ├── permissions.py     # Custom DRF permission classes
    ├── forms.py           # Registration form
    ├── signals.py         # post_save approval handler
    ├── services.py        # Email + X integration helpers
    ├── apps.py            # Connects signals at startup
    ├── admin.py           # Admin registrations
    ├── urls.py            # Web URLs
    ├── api_urls.py        # API URLs (JWT + router)
    ├── tests.py           # 25+ automated tests
    ├── migrations/
    │   ├── 0001_initial.py
    │   ├── 0002_create_role_groups.py
    │   └── 0003_publisher_article_newsletter.py
    └── templates/
        ├── registration/
        │   ├── login.html
        │   └── register.html
        └── news/
            ├── base.html
            ├── home.html
            └── ...
```

---

## Author

**Conor Blake** — HyperionDev AI Engineering Level 2

---