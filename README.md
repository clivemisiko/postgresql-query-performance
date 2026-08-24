# Library Schema

A Django project backed by PostgreSQL. It provides a user-owned `Book` resource and demonstrates a normalized relational schema, database-level constraints, reproducible migrations, seed data, and a Django REST Framework API.

## Requirements

- Python 3.12 or compatible Python version
- PostgreSQL running locally
- A PostgreSQL database and user with permission to create tables

## Setup

Create and activate a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install the pinned dependencies:

```powershell
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root. It is intentionally ignored by Git:

```env
SECRET_KEY=replace-this-for-local-development
DEBUG=True
DB_NAME=library_schema
DB_USER=postgres
DB_PASSWORD=your-postgres-password
DB_HOST=127.0.0.1
DB_PORT=5432
```

Apply the migrations:

```powershell
python manage.py migrate
```

The migrations create the schema and seed two demo users and three books. The demo users are `maya.reader` and `noah.librarian`; their seed password is `library-demo-password` for local demonstration only.

Start Django locally:

```powershell
python manage.py runserver
```

The API is available at `http://127.0.0.1:8000/api/books/`.

## Schema

The main table is `library_book`.

- `owner_id` is a required foreign key to Django's `auth_user` table.
- Deleting a user cascades to that user's books.
- `isbn` is optional but unique when present.
- `title`, `author`, and `owner` are required (`NOT NULL`).
- `book_title_not_blank` rejects empty titles at the database level.
- `book_author_not_blank` rejects empty authors at the database level.
- `created_at` and `updated_at` record row timestamps.

The model definition is in `library/models.py`. Django migrations convert it into PostgreSQL tables, foreign keys, indexes, and constraints.

## Migrations and seed data

Migrations run in this order:

1. `library/migrations/0001_initial.py` creates the `Book` table.
2. `library/migrations/0002_alter_book_isbn_book_book_title_not_blank_and_more.py` adds the unique ISBN field and named check constraints.
3. `library/migrations/0003_seed_library_data.py` creates demo users and books. It includes a reverse operation for removing the seeded rows.

To inspect migration status:

```powershell
python manage.py showmigrations library
```

To confirm there are no model changes missing from migrations:

```powershell
python manage.py makemigrations --check --dry-run
```

## API

All Book API endpoints require authentication. Token authentication is available through `POST /api-token-auth/`; session authentication is available for the browsable API. The token endpoint accepts valid username and password credentials to issue a token.

| Method | Endpoint | Behavior |
| --- | --- | --- |
| `GET` | `/api/books/` | List paginated books |
| `POST` | `/api/books/` | Create a book owned by the authenticated user |
| `GET` | `/api/books/<id>/` | Retrieve one book |
| `PATCH` | `/api/books/<id>/` | Update an owned book |
| `DELETE` | `/api/books/<id>/` | Delete an owned book |
| `POST` | `/api-token-auth/` | Obtain an authentication token |

The list endpoint supports:

- Filtering by `author` and `owner`
- Search across `title`, `author`, and `isbn`
- Ordering by `title`, `author`, and `created_at`
- Page-number pagination with 10 results per page

The serializer validates blank titles/authors and malformed ISBN values. Database constraints remain the final protection for direct database writes and code paths that bypass the API.

## Testing

Run Django's system checks:

```powershell
python manage.py check
```

Run the complete test suite against PostgreSQL:

```powershell
python manage.py test
```

The tests cover API behavior and database constraints, including:

- Successful CRUD operations
- Authentication failures
- Validation failures
- Not-found responses
- Owner-only modification
- Duplicate ISBN rejection by PostgreSQL
- Orphaned foreign-key rejection by PostgreSQL
- `NULL` and blank-value rejection by PostgreSQL



## Important local-development notes

- Use the project's virtual-environment interpreter when running commands: `venv\Scripts\python.exe`.
- Do not commit `.env`, `db.sqlite3`, or the `venv` directory.
- The seed password is for local demonstration only and must not be used in a real deployment.
- This README describes the implemented local project; production deployment, secret management, and operational monitoring are outside this gate.
