from datetime import date, timedelta

from django.test import TestCase

from .models import Author, Book


class BookListPerformanceTests(TestCase):
	def setUp(self):
		self.author = Author.objects.create(
			name="Alex Author",
			email="alex@example.com",
		)
		Book.objects.bulk_create(
			[
				Book(
					title=f"Book {number}",
					isbn=f"978000000000{number}",
					author=self.author,
					published_date=date(2024, 1, 1) + timedelta(days=number),
				)
				for number in range(1, 4)
			]
		)

	def test_book_list_uses_one_query_for_books_and_authors(self):
		with self.assertNumQueries(1):
			response = self.client.get("/books/")

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Book 1 by Alex Author")
		self.assertContains(response, "Book 3 by Alex Author")


class BookIndexTests(TestCase):
	def test_published_date_index_is_declared(self):
		index_names = {index.name for index in Book._meta.indexes}

		self.assertIn("book_pubdate_idx", index_names)
