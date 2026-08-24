# PostgreSQL Query Performance

This project demonstrates Track B, gate B2: **PostgreSQL and data query performance**.

The gate has two related goals:

1. Remove an application-level N+1 query.
2. Add an index for a common sort and prove that PostgreSQL uses it.

The important lesson is that an index should not be judged only by its existence. The query plan and measured execution time must show whether it imprvoves the actual workload.

## Project Performance Path

The relevant request is the book list at `/books/`.

The view displays each book's author name. Without eager loading, Django would run:

```text
1 query to load the books
+ 1 query for each book's author
= N+1 queries
```

The view fixes this with `select_related`:

```python
books = Book.objects.select_related("author").all()
```

Because `author` is a `ForeignKey`, `select_related` uses one SQL join to load books and authors together. The regression test in `library/tests.py` proves the endpoint stays at one query:

```python
with self.assertNumQueries(1):
    response = self.client.get("/books/")
```

`assertNumQueries(1)` is the application-level proof. If `select_related("author")` is removed, accessing `book.author.name` in the view causes additional queries and the test fails.

## Indexing Change

`Book.published_date` is indexed in `library/models.py`:

```python
models.Index(
    fields=["published_date"],
    name="book_pubdate_idx",
)
```

The name means:

- `book`: the model/table being indexed
- `pubdate`: the indexed published-date field
- `idx`: index

The migration `library/migrations/0002_book_book_pubdate_idx.py` creates this index in PostgreSQL. It is an index structure, not a new model field or table.

The index helps this query:

```sql
SELECT id, title, isbn, author_id, published_date
FROM library_book
ORDER BY published_date;
```

An index stores values in an order PostgreSQL can walk. Therefore PostgreSQL can return rows ordered by `published_date` without reading the whole table and sorting every row separately.

## Before and After Evidence

The same query returns the same rows before and after indexing. The index changes the work PostgreSQL performs, not the result set.

The captured benchmark used 50,000 rows:

| State | Plan | Execution time | What happened |
| --- | --- | ---: | --- |
| Before index | `Seq Scan` followed by external merge `Sort` | `63.875 ms` | PostgreSQL read the whole table and sorted rows, spilling 3512 kB to disk |
| After index | `Index Scan using book_pubdate_idx` | `27.757 ms` | PostgreSQL read rows through the index in the required order |

That run showed approximately a **56% reduction** in execution time.

A separate run measured 64.729 ms before the index and 29.681 ms after it. Exact timings vary between runs because of cache state and system load. The durable evidence is the plan change:

```text
Before:
Seq Scan -> external merge Sort

After:
Index Scan using book_pubdate_idx
```

The costly step before indexing was the disk-backed sort:

```text
Sort Method: external merge  Disk: 3512kB
```

The index removes that separate sort operation.

## Reproduce the Application Test

Activate the virtual environment in PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Run Django's checks and tests:

```powershell
python manage.py check
python manage.py test
```

Expected result:

```text
System check identified no issues (0 silenced).
Ran 2 tests ... OK
```

The two tests are:

- The book-list query-count regression test.
- The declaration test for `book_pubdate_idx`.

## Prepare Benchmark Data

The current `library/management/commands/seed_data.py` creates 1,000 books and 50 authors. It deletes the existing books and authors before reseeding:

```powershell
python manage.py seed_data
```

Confirm the actual number of rows in PostgreSQL:

```sql
SELECT count(*) FROM library_book;
```

The number reported by `EXPLAIN ANALYZE` must match the rows currently in the table, not the number written in an old seed run. For example, the earlier benchmark reported 50,000 rows because the database still contained the previous 50,000-row dataset.

For a more visible index benchmark, temporarily change the seed loop to 50,000, run the seed command, and then restore the preferred seed size. The important point is to record the row count alongside the plan and timings.

Refresh PostgreSQL statistics after loading data:

```sql
ANALYZE library_book;
```

## Reproduce the EXPLAIN Comparison

Open PostgreSQL with the database configured in `.env`:

```powershell
psql -U postgres -d queryperf_db
```

First capture the **after-index** plan. The migration must be applied and the index must exist:

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, title, isbn, author_id, published_date
FROM library_book
ORDER BY published_date;
```

Look for:

```text
Index Scan using book_pubdate_idx on library_book
Execution Time: ... ms
```

Now capture the **before-index** plan without permanently deleting the index. Drop it inside a transaction:

```sql
BEGIN;

DROP INDEX book_pubdate_idx;

EXPLAIN (ANALYZE, BUFFERS)
SELECT id, title, isbn, author_id, published_date
FROM library_book
ORDER BY published_date;

ROLLBACK;
```

Look for:

```text
Seq Scan on library_book
Sort Key: published_date
Sort Method: external merge  Disk: ...
Execution Time: ... ms
```

`ROLLBACK` restores the index because the `DROP INDEX` happened inside the transaction. After rollback, run the indexed query again to capture the after-index plan.

## Reading the Plan

`EXPLAIN` displays PostgreSQL's chosen execution plan. `ANALYZE` actually runs the query and reports real row counts and timings. `BUFFERS` reports shared and temporary buffer activity.

### Sequential scan: `Seq Scan`

A sequential scan reads the table from beginning to end. It is visible here because PostgreSQL has no ordered index available after `DROP INDEX`.

### Sort

The sort orders all rows by `published_date`. `external merge` means the sort exceeded available working memory and used temporary disk space. This is the expensive part of the before-index plan.

### Index scan: `Index Scan`

An index scan walks the index and retrieves rows in index order. Because `book_pubdate_idx` is ordered by `published_date`, PostgreSQL can satisfy `ORDER BY published_date` without a separate sort.

The row count should remain the same in both plans. The plan node, buffer behavior, and execution time are what should change.

## File Map

| File | Role in the gate |
| --- | --- |
| `library/models.py` | Defines `Author`, `Book`, and the `published_date` index |
| `library/views.py` | Owns the book-list query and removes the N+1 with `select_related("author")` |
| `library/migrations/0002_book_book_pubdate_idx.py` | Applies the index to PostgreSQL |
| `library/tests.py` | Proves the book list uses one query and checks the index declaration |
| `library/management/commands/seed_data.py` | Creates repeatable benchmark data |
| `docs/b2-query-performance.html` | Visual explanation of the gate and measured evidence |

## Gate Checklist

- [x] N+1 query removed with `select_related`.
- [x] Automated test proves the book list uses one query.
- [x] Index declared for `published_date`.
- [x] Migration created and applied.
- [x] Before and after plans captured with `EXPLAIN (ANALYZE, BUFFERS)`.
- [x] Before plan shows `Seq Scan` plus disk-backed `Sort`.
- [x] After plan shows `Index Scan using book_pubdate_idx`.
- [x] Same row count verified before and after.
