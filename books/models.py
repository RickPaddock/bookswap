from django.db import models
from django.contrib.auth.models import AbstractUser

# slugify removes non-alphanumeric chars to so URLs can be created
from django.template.defaultfilters import slugify
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import misaka  # Misaka allows rendering markdown
import logging

logger = logging.getLogger(__name__)


# User model imports pre-defined django user items. Easier for us.
class CustomUser(AbstractUser):
    location = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.username


class Book(models.Model):
    # Primary identifiers from Google Books API
    google_book_id = models.CharField(max_length=25, primary_key=True)  # volumeInfo.id
    ID_ISBN_13 = models.CharField(max_length=13, null=True, unique=True)  # industryIdentifiers[].identifier (ISBN_13)
    ID_ISBN_10 = models.CharField(max_length=10, null=True, unique=True)  # industryIdentifiers[].identifier (ISBN_10)
    ID_OTHER = models.CharField(max_length=25, null=True, unique=True)  # industryIdentifiers[].identifier (OTHER)

    # Core book information
    title = models.CharField(max_length=100, blank=False)  # volumeInfo.title
    authors = models.CharField(max_length=100, blank=True)  # volumeInfo.authors (joined)
    thumbnail = models.CharField(max_length=600, null=True, blank=True)  # volumeInfo.imageLinks.thumbnail
    description = models.TextField(blank=True)  # volumeInfo.description
    pagecount = models.CharField(max_length=7, null=True, blank=True)  # volumeInfo.pageCount

    # Additional Google Books API fields
    # Date information - Google returns varying formats (YYYY, YYYY-MM, or YYYY-MM-DD)
    published_date = models.CharField(max_length=50, null=True, blank=True)  # volumeInfo.publishedDate

    # Language (ISO 639-1 code, e.g., 'en', 'es', 'fr')
    language = models.CharField(max_length=10, default='en', blank=True)  # volumeInfo.language

    # Categories/Genres (comma-separated from Google Books)
    categories = models.TextField(blank=True)  # volumeInfo.categories (joined with commas)

    # Publisher information
    publisher = models.CharField(max_length=255, blank=True)  # volumeInfo.publisher

    # Rating information from Google Books users
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)  # volumeInfo.averageRating (e.g., 4.5)
    ratings_count = models.PositiveIntegerField(null=True, blank=True)  # volumeInfo.ratingsCount

    # Google Books links
    preview_link = models.URLField(max_length=500, blank=True)  # volumeInfo.previewLink
    info_link = models.URLField(max_length=500, blank=True)  # volumeInfo.infoLink

    # Maturity rating (e.g., "NOT_MATURE" or "MATURE")
    maturity_rating = models.CharField(max_length=20, blank=True)  # volumeInfo.maturityRating

    # Relationship to users
    owner = models.ManyToManyField(CustomUser, through="UserBook")

    def __str__(self):
        return f"{self.title}"


class Group(models.Model):
    group_name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(allow_unicode=True, unique=True)
    description = models.TextField(blank=True, default="")
    description_html = models.TextField(editable=False, default="", blank=True)
    is_private = models.BooleanField(default=False, blank=False)
    members = models.ManyToManyField(CustomUser, through="GroupMember")

    def __str__(self):
        return self.group_name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.group_name)  # Lowercase & replace spaces with hyphens
        self.description_html = misaka.html(self.description)  # Allows markdown
        super().save(
            *args, **kwargs
        )  # Overrides parent class save to include parameters


# Many to Many THROUGH table
class UserBook(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, related_name="book_owners", on_delete=models.CASCADE)

    def __str__(self):
        return f"""{self.user}/{self.book}"""

    @classmethod
    def assign_book_to_user(cls, user, google_book_id):
        book, created = Book.objects.get_or_create(google_book_id=google_book_id)
        user_book, UserBook_created = cls.objects.get_or_create(user=user, book=book)

        return user_book


# Many to Many THROUGH table
class GroupMember(models.Model):
    user = models.ForeignKey(
        CustomUser, related_name="user_groups", on_delete=models.CASCADE
    )
    group = models.ForeignKey(
        Group, related_name="group_memberships", on_delete=models.CASCADE
    )
    admin = models.BooleanField(default=False, blank=False)

    def __str__(self):
        return f"""{self.group}/{self.user}"""

    class Meta:
        unique_together = ("user", "group")

    @classmethod
    def assign_user_to_group(cls, user, group_name):
        group_user, GroupUser_created = cls.objects.get_or_create(
            user=user, group_name=group_name
        )

        return group_user


class Transaction(models.Model):
    owner = models.ForeignKey(
        CustomUser, related_name="book_owner", on_delete=models.CASCADE
    )
    borrower = models.ForeignKey(
        CustomUser, related_name="book_borrower", on_delete=models.CASCADE
    )
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    borrowed_datetime = models.DateTimeField(default=timezone.now, blank=False)
    returned_datetime = models.DateTimeField(null=True, blank=True)

    def clean(self):
        if self.owner not in self.book.owner.all():
            raise ValidationError(
                "The selected book is not owned by the specified owner"
            )

        if self.owner == self.borrower:
            raise ValidationError("Owner and borrower cannot be the same person")

        if (
            self.book.transaction_set.exclude(pk=self.pk)
            .filter(returned_datetime__isnull=True)
            .exists()
        ):
            raise ValidationError(
                "The selected book is already borrowed and has not been returned"
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.returned_datetime:
            return f"{self.borrower.username} returned {self.book.title} to {self.owner.username} on {self.returned_datetime}"
        else:
            return f"{self.borrower.username} borrowed {self.book.title} from {self.owner.username} on {self.borrowed_datetime}"


class Wishlist(models.Model):
    user = models.ForeignKey(
        CustomUser, related_name="user_wish", on_delete=models.CASCADE, blank=False
    )
    book = models.ForeignKey(
        Book, related_name="book_wish", on_delete=models.CASCADE, blank=False
    )
    wished_datetime = models.DateTimeField(default=timezone.now, blank=False)
    removed_datetime = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user}/{self.book}"

    def clean(self):
        if self.user in self.book.owner.all():
            raise ValidationError("The selected book is already owned by the wisher!")

        if (
            self.book.transaction_set.exclude(pk=self.pk)
            .filter(borrower=self.user, returned_datetime__isnull=True)
            .exists()
        ):
            raise ValidationError(
                "The selected book is already borrowed by the wisher!"
            )

    class Meta:
        unique_together = ("user", "book")


# Runs automatically when transaction is created
@receiver(post_save, sender=Transaction)
def update_wishlist_transaction(instance, created, **kwargs):
    """
    Update Wishlist when a user's wish comes true and they lend the book
    """
    # If new transaction is created, then update removed_datetime
    if created:
        if wishlist_entry := Wishlist.objects.filter(
            user=instance.borrower, book=instance.book
        ).first():
            wishlist_entry.removed_datetime = timezone.now()
            wishlist_entry.save()


# Runs automatically when user adds new book ownership
@receiver(post_save, sender=UserBook)
def update_wishlist_ownership(sender, instance, created, **kwargs):
    """
    Update Wishlist when a user now owns the book the wished to have
    """
    # If new ownership is created, then update removed_datetime
    logger.debug("UserBook post_save signal triggered")
    if created:
        logger.debug("New UserBook ownership created, checking wishlist")
        if wishlist_entry := Wishlist.objects.filter(
            user=instance.user, book=instance.book
        ).first():
            wishlist_entry.removed_datetime = timezone.now()
            wishlist_entry.save()


class RequestBook(models.Model):
    owner = models.ForeignKey(
        CustomUser,
        related_name="request_book_owner",
        on_delete=models.CASCADE,
        blank=False,
    )
    requester = models.ForeignKey(
        CustomUser, related_name="book_requester", on_delete=models.CASCADE, blank=False
    )
    book = models.ForeignKey(
        Book, related_name="request_book", on_delete=models.CASCADE, blank=False
    )
    request_datetime = models.DateTimeField(default=timezone.now, blank=False)
    decision = models.BooleanField(null=True, blank=True)
    decision_datetime = models.DateTimeField(null=True, blank=True)
    cancelled_datetime = models.DateTimeField(null=True, blank=True)

    REJECT_REASON_CHOICES = [
        ("Book no longer owned", "Book no longer owned"),
        ("Book already loaned", "Book already loaned"),
        ("I am currently unavailable", "I am currently unavailable"),
        ("Other", "Other"),
    ]

    reject_reason = models.CharField(
        max_length=26, choices=REJECT_REASON_CHOICES, null=True, blank=True
    )

    def __str__(self):
        return f"{self.requester} requested {self.book} from {self.owner}"

    class Meta:
        unique_together = ("owner", "requester", "book", "request_datetime")
