# MindCheck: a private mental-health screening platform

INT402 (Modern Web Programming Tools and Techniques) project, built with **Python 3.10+ and Django 5.2 LTS** on **SQLite**.

MindCheck lets anyone take three standard screening questionnaires in private: **PHQ-9** (depression), **GAD-7** (anxiety) and **WHO-5** (wellbeing). It scores the answers on the server, explains the result in plain language, gives practical next steps, and points to verified support. If PHQ-9 question 9 is answered above 0, a crisis support screen (Tele-MANAS 14416, emergency 112) is shown **before** the result.

> MindCheck screens and signposts. It does **not** diagnose, treat or give medication advice.

---

## 1. Run it (Windows, macOS or Linux)

```bash
# 1. Go into the project folder (the one with manage.py)
cd mindcheck

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS / Linux

# 3. Install Django
pip install -r requirements.txt

# 4. Start the server (the database file db.sqlite3 is already included and filled)
python manage.py runserver
```

Open **http://127.0.0.1:8000/**

### Demo logins

| Role | Username | Password | What they can do |
|---|---|---|---|
| Admin (superuser, counsellor role) | `admin` | `Admin@2026` | Everything, including `/admin/` |
| Counsellor | `counsellor1` | `MindCheck@2026` | Counsellor dashboard, edit guidance, add/edit/delete resources |
| Member | `demo_member` | `MindCheck@2026` | Take screenings, saved history with trend charts, delete data |

Visitors who don't sign in use **private mode**: nothing is written to the database.

### Rebuilding the database from scratch

```bash
del db.sqlite3                  # Windows  (rm db.sqlite3 on macOS/Linux)
python manage.py migrate
python manage.py seed_mindcheck # loads tools, bands, guidance, resources, demo users and made-up history
```

### Other useful commands

```bash
python manage.py test                 # runs all 51 tests
python manage.py createsuperuser      # make your own admin login
python manage.py makemigrations       # after changing a model
python manage.py migrate
set DJANGO_DEBUG=0 && python manage.py runserver --insecure     # Windows: see the custom 404/500 pages
DJANGO_DEBUG=0 python manage.py runserver --insecure            # macOS/Linux
```

---

## 2. How the project was created

```bash
pip install "django>=5.2,<5.3"
django-admin startproject mindcheck_project .
python manage.py startapp accounts
python manage.py startapp screening
python manage.py startapp resources
```

In `mindcheck_project/settings.py`:
- the three apps are added to `INSTALLED_APPS`
- `TEMPLATES["DIRS"] = [BASE_DIR / "templates"]`
- `STATICFILES_DIRS = [BASE_DIR / "static"]`
- a custom context processor `screening.context_processors.site_context` puts the helpline number and the user's role on every page
- session cookies are `HttpOnly` and expire when the browser closes

---

## 3. Folder structure

```
mindcheck/
├── manage.py
├── requirements.txt
├── db.sqlite3                      # filled database (tools, bands, resources, demo users)
├── mindcheck_project/              # project package
│   ├── settings.py
│   ├── urls.py                     # root URLs + handler400/403/404/500
│   └── error_views.py              # custom error pages and CSRF failure page
├── accounts/                       # registration, login, dashboard, delete-my-data
│   ├── models.py                   # Profile (role, consent)
│   ├── forms.py  views.py  urls.py  admin.py  tests.py
├── screening/                      # questionnaires, scoring, crisis flow, history, counsellor area
│   ├── models.py                   # ScreeningTool, Question, AnswerChoice, ScoreBand, Guidance, Assessment
│   ├── scoring.py                  # server-side scoring + safety check
│   ├── forms.py                    # dynamic questionnaire form, guidance form
│   ├── permissions.py              # counsellor_required decorator, consent check
│   ├── context_processors.py
│   ├── templatetags/mindcheck_tags.py   # custom filters: tier_class, percent_of, field_number
│   ├── management/commands/seed_mindcheck.py
│   └── views.py  urls.py  admin.py  tests.py
├── resources/                      # support directory with search and CRUD
│   ├── models.py                   # ResourceCategory, Resource
│   └── forms.py  views.py  urls.py  admin.py  tests.py
├── templates/
│   ├── base.html                   # shared layout and navigation (every page extends it)
│   ├── partials/                   # messages, disclaimer, resource card (included)
│   ├── accounts/  screening/  resources/
│   └── errors/                     # 400, 403, 404, 500
└── static/
    ├── css/style.css               # custom styles, responsive rules
    ├── js/progress.js              # questionnaire progress bar only (no scoring in JS)
    └── vendor/bootstrap/, vendor/chartjs/   # stored locally so the app works offline
```

---

## 4. Database design

| Model | Key fields | Relationships and constraints |
|---|---|---|
| `User` (Django) | username, email, password (hashed) | 1-to-1 with Profile |
| `Profile` | role (member/counsellor), consent_given_at | OneToOne → User (CASCADE), created by a `post_save` signal |
| `ScreeningTool` | name, short_name, slug, score_multiplier, higher_is_better, citation | unique name, short_name and slug |
| `Question` | number, text, is_safety_item | FK → ScreeningTool; unique (tool, number) |
| `AnswerChoice` | value, label | FK → ScreeningTool; unique (tool, value) |
| `Guidance` | tier, severity_rank, headline, advice, retake_after_days | unique tier and rank |
| `ScoreBand` | label, min_score, max_score, interpretation | FK → ScreeningTool, FK → Guidance (PROTECT); check min ≤ max; unique (tool, min_score) |
| `Assessment` | raw_score, final_score, safety_flag, created_at | FK → User (CASCADE), FK → ScreeningTool, FK → ScoreBand (PROTECT); index (user, tool, created_at) |
| `ResourceCategory` | name, slug | unique name and slug |
| `Resource` | name, phone, hours, city, is_crisis_line, last_verified | FK → ResourceCategory (PROTECT), FK → User created_by (SET_NULL); phone regex validator; unique (name, city) |

Questions, choices and bands are **data**, not code: a new questionnaire can be added in the admin without changing any Python.

**Data minimisation:** `Assessment` stores only the totals, band and date. Individual answers and free text are never stored. Private-mode results live only in the session.

---

## 5. URL map

| URL | View | Method | Who |
|---|---|---|---|
| `/` | home | GET | everyone |
| `/about/` | about | GET | everyone |
| `/screening/` | tool_list | GET | everyone |
| `/screening/consent/` | consent | GET, POST | everyone |
| `/screening/take/<slug>/` | take_screening | GET, POST | everyone (after consent) |
| `/screening/support/` | crisis | GET | after a flagged answer |
| `/screening/result/<int:pk>/` | result | GET | owner only (others get 404) |
| `/screening/result/private/` | session_result | GET | private-mode visitor |
| `/screening/result/private/clear/` | clear_session_result | POST | private-mode visitor |
| `/screening/history/?tool=&tier=` | history | GET | signed-in member |
| `/screening/history/<int:pk>/delete/` | delete_assessment | GET, POST | owner |
| `/screening/counsellor/` | counsellor_dashboard | GET | counsellor |
| `/screening/counsellor/guidance/<tier>/edit/` | edit_guidance | GET, POST | counsellor |
| `/resources/?q=&category=&crisis_only=&page=` | resource_list (search) | GET | everyone |
| `/resources/category/<slug>/` | resource_list | GET | everyone |
| `/resources/<int:pk>/` | resource_detail | GET | everyone |
| `/resources/add/` | resource_create | GET, POST | counsellor |
| `/resources/<int:pk>/edit/` | resource_update | GET, POST | counsellor |
| `/resources/<int:pk>/delete/` | resource_delete | GET, POST | counsellor |
| `/accounts/register/`, `/login/` | register, login | GET, POST | everyone |
| `/accounts/logout/` | logout | POST | signed in |
| `/accounts/dashboard/` | dashboard | GET | signed in |
| `/accounts/delete-my-data/` | delete_my_data | GET, POST | signed in |
| `/admin/` | Django admin (customised) | | staff |

---

## 6. Scoring rules (checked by tests)

| Tool | Items × values | Score | Bands → action tier |
|---|---|---|---|
| PHQ-9 | 9 × 0–3 | 0–27 | 0–4 Minimal (Low), 5–9 Mild, 10–14 Moderate, 15–19 Moderately severe (High), 20–27 Severe (High) |
| GAD-7 | 7 × 0–3 | 0–21 | 0–4 Minimal, 5–9 Mild, 10–14 Moderate, 15–21 Severe (High) |
| WHO-5 | 5 × 0–5 | raw × 4 = 0–100 | 0–28 Very low wellbeing (High), 29–49 Low wellbeing (Moderate), 50–100 Good (Low) |

- The WHO-5 multiplier is applied **before** the band is looked up.
- PHQ-9 item 9 > 0 → crisis screen first. The result page itself also redirects to the crisis screen if it hasn't been shown, so the screen can't be skipped by typing the URL.
- All scoring runs in `screening/scoring.py` on the server; `progress.js` only moves the progress bar.

---

## 7. Security checklist

- Passwords hashed by Django (PBKDF2) and checked with Django's password validators
- ORM queries only, so no raw SQL and no SQL injection
- Template auto-escaping blocks cross-site scripting
- CSRF token on every POST form; logout is POST-only; custom CSRF failure page
- Session key rotated on login; `HttpOnly` cookies; `X-Frame-Options: DENY`
- Ownership checks: `get_object_or_404(..., user=request.user)`
- Role checks: `counsellor_required` decorator returns the custom 403 page
- Redirect target after consent must be a local path (no open redirect)

---

## 8. Before the demo

- Replace the placeholder phone numbers for **University Counselling Cell** and **Civil Hospital** with real ones (Counsellor area → Manage directory → Edit), and update the "last verified" date.
- Tele-MANAS (14416 / 1-800-891-4416) and 112 were checked on 14 Nov 2026.
- Use only made-up answer profiles in the demo. Never ask classmates to answer with their real feelings.

## References

- Kroenke K, Spitzer RL, Williams JBW (2001). The PHQ-9. *J Gen Intern Med* 16(9):606–613.
- Spitzer RL, Kroenke K, Williams JBW, Löwe B (2006). The GAD-7. *Arch Intern Med* 166(10):1092–1097.
- WHO Regional Office for Europe (1998). *Wellbeing Measures in Primary Health Care: the DepCare Project.*
- Digital Personal Data Protection Act, 2023 (India).
- Django 5.2 documentation, https://docs.djangoproject.com/en/5.2/
