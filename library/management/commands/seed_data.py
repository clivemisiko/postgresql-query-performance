import random

from django.core.management.base import BaseCommand
from faker import Faker

from library.models import Author, Book


class Command(BaseCommand):
    help = "Seed the database with sample authors and books."

    def handle(self, *args, **options):
        fake = Faker()

        Book.objects.all().delete()
        Author.objects.all().delete()

        authors = [
            Author.objects.create(name=fake.name(), email=fake.unique.email())
            for _ in range(50)
        ]
        self.stdout.write(f"Created {len(authors)} authors.")

        for _ in range(50,000):
            Book.objects.create(
                title=fake.sentence(nb_words=4),
                isbn=fake.unique.isbn13(separator=""),
                author=random.choice(authors),
                published_date=fake.date_between(start_date="-30y", end_date="today"),
            )
        self.stdout.write("Created 50,000 books.")