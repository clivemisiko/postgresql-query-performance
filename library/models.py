from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)

    def __str__(self) -> str:
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=200)
    isbn = models.CharField(max_length=13, unique=True)
    author = models.ForeignKey(
        Author,
        on_delete=models.CASCADE,
        related_name="books",
    )
    published_date = models.DateField()

    class Meta:
        indexes = [
            models.Index(fields=["published_date"], name="book_pubdate_idx"),
        ]

    def __str__(self) -> str:
        return self.title

