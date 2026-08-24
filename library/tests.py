from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Book

User = get_user_model()


class BookApiTests(APITestCase):
	def setUp(self):
		self.owner = User.objects.create_user(username="owner", password="test-pass")
		self.other_user = User.objects.create_user(
			username="other", password="test-pass"
		)
		self.book = Book.objects.create(
			title="Django for APIs",
			author="Alex Author",
			isbn="1234567890",
			owner=self.owner,
		)
		self.list_url = "/api/books/"

	def authenticate(self, user):
		self.client.force_authenticate(user=user)

	def test_list_requires_authentication(self):
		response = self.client.get(self.list_url)

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_create_requires_authentication(self):
		response = self.client.post(
			self.list_url,
			{"title": "Unauthenticated", "author": "Visitor"},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_list_is_paginated_and_filterable(self):
		self.authenticate(self.owner)

		response = self.client.get(self.list_url, {"author": "Alex Author"})

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data["count"], 1)
		self.assertEqual(response.data["results"][0]["id"], self.book.id)

	def test_create_assigns_authenticated_owner(self):
		self.authenticate(self.owner)

		response = self.client.post(
			self.list_url,
			{"title": "Clean Code", "author": "Robert Martin", "isbn": "1234567890123"},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data["owner"], self.owner.username)
		self.assertEqual(Book.objects.get(id=response.data["id"]).owner, self.owner)

	def test_create_rejects_invalid_payload(self):
		self.authenticate(self.owner)

		response = self.client.post(
			self.list_url,
			{"title": "   ", "author": "Author", "isbn": "bad-isbn"},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn("title", response.data)
		self.assertIn("isbn", response.data)

	def test_update_rejects_invalid_payload(self):
		self.authenticate(self.owner)
		detail_url = f"{self.list_url}{self.book.id}/"

		response = self.client.patch(
			detail_url, {"isbn": "bad-isbn"}, format="json"
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn("isbn", response.data)

	def test_detail_update_and_delete_succeed_for_owner(self):
		self.authenticate(self.owner)
		detail_url = f"{self.list_url}{self.book.id}/"

		detail_response = self.client.get(detail_url)
		update_response = self.client.patch(
			detail_url, {"title": "Updated title"}, format="json"
		)
		delete_response = self.client.delete(detail_url)

		self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
		self.assertEqual(update_response.status_code, status.HTTP_200_OK)
		self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
		self.assertFalse(Book.objects.filter(id=self.book.id).exists())

	def test_detail_operations_return_not_found_for_missing_book(self):
		self.authenticate(self.owner)
		detail_url = f"{self.list_url}999999/"

		for method in (self.client.get, self.client.patch, self.client.delete):
			response = method(detail_url, {"title": "Missing"}, format="json") \
				if method == self.client.patch else method(detail_url)
			self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

	def test_non_owner_cannot_modify_another_users_book(self):
		self.authenticate(self.other_user)
		detail_url = f"{self.list_url}{self.book.id}/"

		response = self.client.patch(
			detail_url, {"title": "Unauthorized change"}, format="json"
		)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
		self.book.refresh_from_db()
		self.assertEqual(self.book.title, "Django for APIs")

	def test_detail_write_operations_require_authentication(self):
		detail_url = f"{self.list_url}{self.book.id}/"

		update_response = self.client.patch(
			detail_url, {"title": "Unauthenticated change"}, format="json"
		)
		delete_response = self.client.delete(detail_url)

		self.assertEqual(update_response.status_code, status.HTTP_401_UNAUTHORIZED)
		self.assertEqual(delete_response.status_code, status.HTTP_401_UNAUTHORIZED)


class BookDatabaseConstraintTests(TransactionTestCase):
	def setUp(self):
		self.owner = User.objects.create_user(username="constraint-owner")
		self.book_data = {
			"title": "Database Reliability",
			"author": "Test Author",
			"isbn": "9780000000001",
			"owner": self.owner,
		}

	def test_unique_isbn_is_enforced_by_database(self):
		Book.objects.create(**self.book_data)

		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				Book.objects.create(
					**{**self.book_data, "title": "Duplicate ISBN"}
				)

	def test_owner_foreign_key_rejects_orphaned_reference(self):
		book = Book.objects.create(**self.book_data)
		table = connection.ops.quote_name(Book._meta.db_table)

		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				with connection.cursor() as cursor:
					cursor.execute(
						f"UPDATE {table} SET owner_id = %s WHERE id = %s",
						[999999, book.pk],
					)

	def test_not_null_and_check_constraints_reject_invalid_rows(self):
		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				Book.objects.create(**{**self.book_data, "title": None})

		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				Book.objects.create(**{**self.book_data, "title": ""})
