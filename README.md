# DevTrack — Engineering Issue Tracking Backend API

DevTrack is a production-grade backend service built with Django and Django REST Framework for tracking software engineering issues, reporters, assignments, labels, and workflow lifecycles.

---

## 1. Overview & Architecture

DevTrack follows a strict layered architecture that decouples input parsing, business invariants, workflow execution, and presentation.

```
       [ HTTP Clients / Postman / Swagger UI ]
                          │
                          ▼
            [ Exception Handler & Throttling ]
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
   [ Brief API (/api/) ]          [ Advanced API (/api/v1/) ]
   - Public & frozen              - Authenticated (Token)
   - Strict shape checks          - Roles (admin, developer, viewer)
          │                               │
          └───────────────┬───────────────┘
                          ▼
              [ Serializers & Validation ]
       (Shape checks & EntityValidationMixin)
                          │
                          ▼
              [ Services Layer (Writes) ]
           (Atomic Transactions & History)
                          │
                          ▼
            [ Domain Models (validate()) ]
          (Single Source of Business Truth)
                          │
                          ▼
             [ PostgreSQL / SQLite DB ]
```

---

## 2. Features

### Required by the Brief
- **Reporter Management**: Register reporters, enforce unique IDs, valid emails, and required teams.
- **Issue Tracking**: Create issues linked to valid reporters with validation on statuses and priorities.
- **Polymorphic Messages**: Dynamically format status descriptions based on priority (`CriticalIssue` em dash urgent notice, `LowPriorityIssue` notice, default bracketed priority).
- **Brief Compatibility**: Retains the exact JSON payload shapes and custom error messages defined in the initial specification.

### Beyond the Brief
- **Two API Surfaces**: Public `/api/` for the brief contract; versioned `/api/v1/` with full REST capabilities.
- **Role-Based Access Control (RBAC)**: Groups for `admin`, `developer`, and `viewer` with granular action and object-level permissions.
- **Workflow State Engine**: Finite status transitions (`open` → `in_progress` → `resolved` / `closed`) with automated `resolved_at` timestamps.
- **Immutable Status History**: Audit trail recording every status change, timestamp, and actor.
- **Collaboration**: Commenting threads and tagging with case-insensitive unique labels and hex color validation.
- **Advanced Querying**: Filters (status, priority, reporter, `assignee=me`, `unassigned=true`, active, date ranges), full-text search, and rank-based ordering.
- **Query Optimization**: Constant query count (`assertNumQueries <= 5`) regardless of page size using `select_related`, `prefetch_related`, and annotations.
- **Insights & Metrics**: Real-time `/api/v1/dashboard/` and system-wide `/api/v1/statistics/` with resolution time analysis and 30-day activity timeline.
- **Interactive OpenAPI Documentation**: Full Swagger UI (`/api/docs/`) and OpenAPI 3.0 schema generation (`/api/schema/`).

---

## 3. Tech Stack & Project Structure

- **Framework**: Django 6.1, Django REST Framework 3.16
- **Database**: PostgreSQL (Production/Dev), SQLite (In-Memory Test Runner)
- **API Documentation**: `drf-spectacular` (OpenAPI 3.0)
- **Filtering**: `django-filter`

```
DEVTRACK/
├── dev_tracker/
│   ├── settings.py         # App configuration, auth classes, throttles, and spectacular settings
│   ├── urls.py             # Root URL routing, Swagger UI, and OpenAPI schema routes
│   └── wsgi.py             # WSGI entrypoint for web server deployment
├── issues/
│   ├── admin.py            # Django Admin registration and read-only inlines
│   ├── apps.py             # AppConfig loading signals on ready()
│   ├── exceptions.py       # Custom exception handler normalizing brief and v1 error formats
│   ├── filters.py          # IssueFilter, ReporterFilter, and PriorityAwareOrderingFilter
│   ├── models.py           # Domain models, validate() invariants, proxy classes, and IssueQuerySet
│   ├── permissions.py      # RBAC roles helper and custom DRF permission classes
│   ├── serializers.py      # Shape serializers, EntityValidationMixin, and response models
│   ├── services.py         # Atomic transactional business operations and state transitions
│   ├── signals.py          # Auto-assignment of new non-superusers to the 'viewer' group
│   ├── urls.py             # Dual routing: brief endpoints and v1 DefaultRouter patterns
│   ├── views.py            # Brief APIViews, v1 ModelViewSets, and Insights views
│   ├── management/
│   │   └── commands/
│   │       └── seed_demo.py # Management command to populate realistic sample data
│   └── tests/
│       ├── helpers.py      # Test factories and authenticated client utilities
│       ├── test_auth_api.py       # Authentication, registration, logout, and token tests
│       ├── test_brief_api.py      # 30-step acceptance matrix for the frozen brief contract
│       ├── test_collaboration_api.py # Comments, label attachments, and history tests
│       ├── test_dashboard_api.py  # Dashboard and statistics aggregations tests
│       ├── test_issues_api.py     # Issues CRUD, filtering, ordering, and query bounds
│       ├── test_models.py         # Model validation rules, proxy classes, and transitions
│       ├── test_permissions.py    # Role matrix and object-level permission enforcement
│       ├── test_reporters_api.py  # Reporters CRUD, conflict prevention (409), and pagination
│       ├── test_serializers.py    # Strict field types and EntityValidationMixin tests
│       └── test_services.py       # Transactional rollbacks, history generation, and assignments
├── manage.py               # Django management utility
└── requirements.txt        # Python package dependencies
```

---

## 4. Getting Started

### Prerequisites
- Python 3.12+ / Conda environment `django_env`
- PostgreSQL running locally or via Docker

### Setup Instructions

1. **Activate the environment**:
   ```bash
   conda activate django_env
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Ensure `.env` exists in the project root:
   ```env
   DB_NAME=dev_tracer
   DB_USER=devtracer_user
   DB_PASSWORD=dev@123
   DB_HOST=localhost
   DB_PORT=5432
   ```

4. **Run Migrations**:
   ```bash
   python manage.py migrate
   ```

5. **Seed Demo Data**:
   Populate roles, demo users, reporters, labels, and issues:
   ```bash
   python manage.py seed_demo --force
   ```

6. **Create Superuser (Optional)**:
   ```bash
   python manage.py createsuperuser
   ```

7. **Start Development Server**:
   ```bash
   python manage.py runserver
   ```
   Base URL: `http://127.0.0.1:8000/`  
   Swagger UI: `http://127.0.0.1:8000/api/docs/`

8. **Run Test Suite**:
   ```bash
   python manage.py test
   ```
   *(All 44 automated tests run against an isolated SQLite test database).*

---

## 5. Two API Surfaces

DevTrack exposes two distinct API surfaces:

1. **Brief Surface (`/api/`)**:
   - Designed to strictly satisfy the original brief's requirements.
   - Publicly accessible (no authentication required).
   - Unpaginated raw JSON arrays and objects.
   - Exact custom error messages (`{"error": "<message>"}`).
   - Can be toggled via `BRIEF_API_ENABLED = True/False` in `settings.py`.

2. **Advanced Surface (`/api/v1/`)**:
   - Industry-standard REST API designed for frontend web/mobile clients.
   - Protected by Token Authentication.
   - Standard envelope pagination (`count`, `next`, `previous`, `results`).
   - Detailed machine-readable error responses (`error`, `code`, `details`).

---

## 6. Authentication & Roles

### Authentication Flow
1. Obtain an API token by registering (`/api/v1/auth/register/`) or logging in (`/api/v1/auth/login/`).
2. Attach the token to the HTTP `Authorization` header in all requests:
   ```http
   Authorization: Token <your_token_key>
   ```

### Demo Accounts (Created by `seed_demo`)
| Username | Password | Role | Permissions |
| :--- | :--- | :--- | :--- |
| `admin_demo` | `AdminPass123!` | `admin` | Full control: delete entities, reassign any ticket, change user roles |
| `dev_demo` | `DevPass123!` | `developer` | Create issues, edit tickets created by or assigned to them, comment |
| `viewer_demo` | `ViewerPass123!` | `viewer` | Read-only access across all v1 resources |

### Role Permissions Matrix
| Action | Anonymous | Viewer | Developer | Admin |
| :--- | :---: | :---: | :---: | :---: |
| Register / Login | ✓ | ✓ | ✓ | ✓ |
| Read reporters, issues, labels, comments, history | ✗ (401) | ✓ | ✓ | ✓ |
| Create reporter / label | ✗ | ✗ (403) | ✓ | ✓ |
| Update reporter / label | ✗ | ✗ | ✓ | ✓ |
| Delete reporter / label | ✗ | ✗ | ✗ | ✓ |
| Create issue | ✗ | ✗ | ✓ | ✓ |
| Update / transition / assign an issue | ✗ | ✗ | Creator or Assignee only | ✓ |
| Delete issue | ✗ | ✗ | ✗ | ✓ |
| Add comment | ✗ | ✗ | ✓ | ✓ |
| Edit / delete comment | ✗ | ✗ | Author only | ✓ |
| Change user roles | ✗ | ✗ | ✗ | ✓ |

---

## 7. Endpoint Reference

### Brief API (`/api/`)
| Method | Endpoint | Description | Status Codes |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/reporters/` | List all reporters | `200` |
| `POST` | `/api/reporters/` | Create a reporter | `201`, `400` |
| `GET` | `/api/reporters/?id={id}` | Retrieve single reporter | `200`, `400`, `404` |
| `GET` | `/api/issues/` | List all issues | `200` |
| `POST` | `/api/issues/` | Create an issue (returns formatted message) | `201`, `400` |
| `GET` | `/api/issues/?id={id}` | Retrieve single issue | `200`, `400`, `404` |
| `GET` | `/api/issues/?status={status}` | Filter issues by status | `200`, `400` |

### Advanced API (`/api/v1/`)
| Method | Endpoint | Permission | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register/` | Public | Register new user (defaults to `viewer`) |
| `POST` | `/api/v1/auth/login/` | Public | Authenticate and obtain API token |
| `POST` | `/api/v1/auth/logout/` | Authenticated | Revoke current token |
| `GET` | `/api/v1/auth/me/` | Authenticated | Retrieve current user profile and role |
| `GET` | `/api/v1/users/` | Authenticated | List users for assignment pickers |
| `POST` | `/api/v1/users/{id}/set-role/` | Admin | Change user role (`admin`, `developer`, `viewer`) |
| `GET`, `POST` | `/api/v1/reporters/` | Read: Any, Write: Dev+ | List / Create reporters |
| `GET`, `PATCH`, `DELETE` | `/api/v1/reporters/{id}/` | Delete: Admin | Retrieve, update, or delete reporter (409 if has issues) |
| `GET` | `/api/v1/reporters/{id}/issues/` | Authenticated | Paginated issues belonging to reporter |
| `GET`, `POST` | `/api/v1/labels/` | Read: Any, Write: Dev+ | List / Create labels |
| `GET`, `PATCH`, `DELETE` | `/api/v1/labels/{id}/` | Delete: Admin | Retrieve, update, delete label |
| `GET`, `POST` | `/api/v1/issues/` | Read: Any, Write: Dev+ | List / Create issues |
| `GET`, `PATCH`, `DELETE` | `/api/v1/issues/{id}/` | Update: Editor, Delete: Admin | Retrieve, update, delete issue |
| `POST` | `/api/v1/issues/{id}/transition/` | Issue Editor | Transition status (`status`, `note`) |
| `POST` | `/api/v1/issues/{id}/assign/` | Issue Editor | Assign ticket (`assignee` ID or `null`) |
| `GET` | `/api/v1/issues/{id}/history/` | Authenticated | Audit history of status changes |
| `GET`, `POST` | `/api/v1/issues/{id}/comments/` | Read: Any, Write: Dev+ | List / Add comments |
| `PATCH`, `DELETE` | `/api/v1/issues/{id}/comments/{cid}/`| Author or Admin | Edit / Delete comment |
| `GET`, `POST` | `/api/v1/issues/{id}/labels/` | Write: Editor | View / Idempotently attach label |
| `DELETE` | `/api/v1/issues/{id}/labels/{lid}/` | Issue Editor | Detach label from issue |
| `GET` | `/api/v1/dashboard/` | Authenticated | Personal user dashboard metrics |
| `GET` | `/api/v1/statistics/` | Authenticated | Global issue analytics, resolution time, 30-day trend |

---

## 8. Request & Response Examples

### 1. Create Issue (Brief API)
**Request:**
```http
POST /api/issues/ HTTP/1.1
Content-Type: application/json

{
  "title": "Login button not working on mobile",
  "description": "The login button is unclickable on screens smaller than 768px.",
  "status": "open",
  "priority": "critical",
  "reporter_id": 1
}
```

**Response (`201 Created`):**
```json
{
  "id": 1,
  "title": "Login button not working on mobile",
  "description": "The login button is unclickable on screens smaller than 768px.",
  "status": "open",
  "priority": "critical",
  "reporter_id": 1,
  "created_at": "2026-10-10T23:00:00Z",
  "message": "[URGENT] Login button not working on mobile — needs immediate attention"
}
```

### 2. Validation Error (Brief API)
**Request:**
```http
POST /api/issues/ HTTP/1.1
Content-Type: application/json

{
  "title": "",
  "description": "Missing title test",
  "status": "open",
  "priority": "medium",
  "reporter_id": 1
}
```

**Response (`400 Bad Request`):**
```json
{
  "error": "Title cannot be empty"
}
```

### 3. Transition Issue Status (v1 API)
**Request:**
```http
POST /api/v1/issues/1/transition/ HTTP/1.1
Authorization: Token 4a7f92b109...
Content-Type: application/json

{
  "status": "in_progress",
  "note": "Beginning triage on iOS Simulator"
}
```

**Response (`200 OK`):**
```json
{
  "id": 1,
  "title": "Login button not working on mobile",
  "status": "in_progress",
  "priority": "critical",
  "reporter": { "id": 1, "name": "Asha Rao" },
  "updated_at": "2026-10-10T23:05:00Z"
}
```

---

## 9. Design Decision

> **Core Architectural Decision**:  
> *"Business invariants and validation rules live exclusively in domain model `validate()` methods; serializers validate shape and type constraints, while services own transactional persistence."*

### Rationale:
1. **Single Source of Truth**: By maintaining core rules (such as `Title cannot be empty`, allowed status values, and hex color formatting) in `model.validate()`, the exact business messages defined in the specification survive across every interface: the Brief API, the v1 API, the Django Admin, and seed commands.
2. **Decoupled Writes**: Complex side effects (e.g. automatically writing a `StatusHistory` record or enforcing atomic transitions) are kept out of serializers and viewsets. They are encapsulated in `issues/services.py` within `transaction.atomic()` blocks, ensuring complete rollback on failure.
3. **Zero Extra Tables for Polymorphism**: Utilizing Django Proxy Models (`CriticalIssue`, `LowPriorityIssue`) provides priority-specific `describe()` messages without introducing unnecessary database tables or joins.

---

## 10. Deviation Notes
- **Database Storage**: The brief references storing data in local JSON files. In DevTrack, PostgreSQL with the Django ORM is used to ensure thread safety, ACID transaction guarantees, and production durability.
- **Superset Timestamps**: Brief responses include `created_at` alongside the sample fields, providing accurate auditing while maintaining 100% field compatibility.

---

## 11. Limitations & Future Work
- **Authentication**: Token authentication is used. Refresh tokens via JWT (JSON Web Tokens) or OAuth2 can be added in future iterations.
- **File Attachments**: Direct issue file and screenshot attachments are planned for the next release.
- **Real-Time Notifications**: WebSockets / Django Channels integration for live issue updates on collaborative boards.
