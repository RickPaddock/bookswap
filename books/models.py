from django.db import models
from django.contrib.auth.models import AbstractUser

# slugify removes non-alphanumeric chars to so URLs can be created
from django.template.defaultfilters import slugify
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


# User model imports pre-defined django user items. Easier for us.
class CustomUser(AbstractUser):
    location = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.username


class Book(models.Model):
    ID_ISBN_13 = models.CharField(max_length=13, null=True, unique=True)
    ID_ISBN_10 = models.CharField(max_length=10, null=True, unique=True)
    ID_OTHER = models.CharField(max_length=25, null=True, unique=True)
    google_book_id = models.CharField(max_length=25, unique=True, blank=False)
    title = models.CharField(max_length=100, blank=False)
    authors = models.CharField(max_length=100, blank=True)
    thumbnail = models.ImageField(upload_to="images", null=True, blank=True)
    description = models.CharField(max_length=500, blank=True)
    pagecount = models.CharField(max_length=7, null=True, blank=True)
    owner = models.ManyToManyField(CustomUser, through="UserBook")

    def __str__(self):
        return f"{self.title}"


class Group(models.Model):
    group_name = models.CharField(max_length=255, unique=True)
    # SLUG only contains letters, numbers, underscores, or hyphens
    slug = models.SlugField(allow_unicode=True, unique=True)
    description = models.TextField(blank=True, default="")
    is_private = models.BooleanField(default=False, blank=False)
    members = models.ManyToManyField(CustomUser, through="GroupMember")

    def __str__(self):
        return self.group_name


# Many to Many THROUGH table
# TODO: User can have more than 1 copy so not unique by name/book
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
def update_wishlist(instance, created, **kwargs):
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
