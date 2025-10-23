"""
Unit tests for BookSwap models - focusing on Transaction and Wishlist
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from books.models import Transaction, Wishlist, UserBook, Book
from django.contrib.auth import get_user_model

User = get_user_model()


# ============================================================================
# TRANSACTION MODEL TESTS
# ============================================================================

class TestTransactionModel(TestCase):
    """Test cases for Transaction model - CRITICAL validation logic"""

    def setUp(self):
        """Set up test data for each test method"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.user2 = User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            password="testpass123"
        )
        self.user3 = User.objects.create_user(
            username="testuser3",
            email="test3@example.com",
            password="testpass123"
        )
        self.book = Book.objects.create(
            google_book_id="test_book_001",
            title="Test Book Title",
            authors="Test Author",
            description="A test book description",
            pagecount="250"
        )
        self.book2 = Book.objects.create(
            google_book_id="test_book_002",
            title="Second Test Book",
            authors="Another Author",
            description="Another test book",
            pagecount="300"
        )

    def test_create_valid_transaction(self):
        """Test creating a valid transaction where owner lends to borrower"""
        # User must own the book first
        UserBook.objects.create(user=self.user, book=self.book)

        transaction = Transaction.objects.create(
            owner=self.user,
            borrower=self.user2,
            book=self.book
        )

        self.assertIsNotNone(transaction.pk)
        self.assertEqual(transaction.owner, self.user)
        self.assertEqual(transaction.borrower, self.user2)
        self.assertEqual(transaction.book, self.book)
        self.assertIsNotNone(transaction.borrowed_datetime)
        self.assertIsNone(transaction.returned_datetime)

    def test_borrowed_datetime_auto_set(self):
        """Test that borrowed_datetime is automatically set on creation"""
        UserBook.objects.create(user=self.user, book=self.book)

        before_creation = timezone.now()
        transaction = Transaction.objects.create(
            owner=self.user,
            borrower=self.user2,
            book=self.book
        )
        after_creation = timezone.now()

        self.assertGreaterEqual(transaction.borrowed_datetime, before_creation)
        self.assertLessEqual(transaction.borrowed_datetime, after_creation)

    def test_returned_datetime_none_on_creation(self):
        """Test that returned_datetime is None when transaction is created"""
        UserBook.objects.create(user=self.user, book=self.book)

        transaction = Transaction.objects.create(
            owner=self.user,
            borrower=self.user2,
            book=self.book
        )

        self.assertIsNone(transaction.returned_datetime)

    def test_owner_must_own_book_validation(self):
        """Test that owner must actually own the book (CRITICAL validation)"""
        # self.user does not own the book (no UserBook entry)
        with self.assertRaises(ValidationError) as context:
            Transaction.objects.create(
                owner=self.user,
                borrower=self.user2,
                book=self.book
            )

        self.assertIn("not owned by the specified owner", str(context.exception))

    def test_owner_cannot_borrow_from_themselves(self):
        """Test that owner and borrower cannot be the same person"""
        UserBook.objects.create(user=self.user, book=self.book)

        with self.assertRaises(ValidationError) as context:
            Transaction.objects.create(
                owner=self.user,
                borrower=self.user,  # Same as owner
                book=self.book
            )

        self.assertIn("Owner and borrower cannot be the same person", str(context.exception))

    def test_book_already_borrowed_validation(self):
        """Test that a book already borrowed cannot be borrowed again"""
        UserBook.objects.create(user=self.user, book=self.book)

        # Create first transaction (book is now borrowed)
        Transaction.objects.create(
            owner=self.user,
            borrower=self.user2,
            book=self.book
        )

        # Try to create second transaction for same book (should fail)
        with self.assertRaises(ValidationError) as context:
            Transaction.objects.create(
                owner=self.user,
                borrower=self.user3,
                book=self.book
            )

        self.assertIn("already borrowed and has not been returned", str(context.exception))

    def test_book_can_be_borrowed_after_return(self):
        """Test that a book can be borrowed again after being returned"""
        UserBook.objects.create(user=self.user, book=self.book)

        # Create first transaction
        transaction1 = Transaction.objects.create(
            owner=self.user,
            borrower=self.user2,
            book=self.book
        )

        # Mark as returned
        transaction1.returned_datetime = timezone.now()
        transaction1.save()

        # Now the book can be borrowed again
        transaction2 = Transaction.objects.create(
            owner=self.user,
            borrower=self.user3,
            book=self.book
        )

        self.assertIsNotNone(transaction2.pk)
        self.assertEqual(transaction2.borrower, self.user3)

    def test_set_returned_datetime(self):
        """Test setting returned_datetime when book is returned"""
        UserBook.objects.create(user=self.user, book=self.book)

        transaction = Transaction.objects.create(
            owner=self.user,
            borrower=self.user2,
            book=self.book
        )

        # Initially None
        self.assertIsNone(transaction.returned_datetime)

        # Set return time
        return_time = timezone.now()
        transaction.returned_datetime = return_time
        transaction.save()

        # Verify it was saved
        transaction.refresh_from_db()
        self.assertEqual(transaction.returned_datetime, return_time)

    def test_transaction_str_active(self):
        """Test __str__ representation for active (unreturned) transaction"""
        UserBook.objects.create(user=self.user, book=self.book)

        transaction = Transaction.objects.create(
            owner=self.user,
            borrower=self.user2,
            book=self.book
        )

        str_repr = str(transaction)
        self.assertIn(self.user2.username, str_repr)
        self.assertIn("borrowed", str_repr)
        self.assertIn(self.book.title, str_repr)
        self.assertIn(self.user.username, str_repr)

    def test_transaction_str_returned(self):
        """Test __str__ representation for returned transaction"""
        UserBook.objects.create(user=self.user, book=self.book)

        transaction = Transaction.objects.create(
            owner=self.user,
            borrower=self.user2,
            book=self.book
        )
        transaction.returned_datetime = timezone.now()
        transaction.save()

        str_repr = str(transaction)
        self.assertIn(self.user2.username, str_repr)
        self.assertIn("returned", str_repr)
        self.assertIn(self.book.title, str_repr)
        self.assertIn(self.user.username, str_repr)

    def test_multiple_users_can_own_same_book_sequentially(self):
        """Test that multiple users can own and lend the same book sequentially"""
        # self.user and self.user2 both own the book
        UserBook.objects.create(user=self.user, book=self.book)
        UserBook.objects.create(user=self.user2, book=self.book)

        # self.user lends to self.user3
        transaction1 = Transaction.objects.create(
            owner=self.user,
            borrower=self.user3,
            book=self.book
        )

        # Mark as returned
        transaction1.returned_datetime = timezone.now()
        transaction1.save()

        # Now self.user2 can also lend the same book (after first one returned)
        user4 = User.objects.create_user(username="user4", email="user4@test.com", password="pass")
        transaction2 = Transaction.objects.create(
            owner=self.user2,
            borrower=user4,
            book=self.book
        )

        self.assertNotEqual(transaction1.pk, transaction2.pk)
        self.assertEqual(Transaction.objects.filter(book=self.book).count(), 2)

    def test_query_active_transactions(self):
        """Test querying for active (unreturned) transactions"""
        UserBook.objects.create(user=self.user, book=self.book)
        UserBook.objects.create(user=self.user, book=self.book2)

        # Create 2 transactions, return only 1
        transaction1 = Transaction.objects.create(owner=self.user, borrower=self.user2, book=self.book)
        transaction1.returned_datetime = timezone.now()
        transaction1.save()

        transaction2 = Transaction.objects.create(owner=self.user, borrower=self.user3, book=self.book2)

        # Query active transactions
        active = Transaction.objects.filter(returned_datetime__isnull=True)

        self.assertEqual(active.count(), 1)
        self.assertIn(transaction2, active)
        self.assertNotIn(transaction1, active)

    def test_transaction_foreign_key_cascade(self):
        """Test that deleting user cascades to delete transactions"""
        UserBook.objects.create(user=self.user, book=self.book)

        transaction = Transaction.objects.create(
            owner=self.user,
            borrower=self.user2,
            book=self.book
        )
        transaction_id = transaction.pk

        # Delete borrower
        self.user2.delete()

        # Transaction should be deleted
        self.assertFalse(Transaction.objects.filter(pk=transaction_id).exists())


# ============================================================================
# WISHLIST MODEL TESTS
# ============================================================================

class TestWishlistModel(TestCase):
    """Test cases for Wishlist model - CRITICAL validation logic"""

    def setUp(self):
        """Set up test data for each test method"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.user2 = User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            password="testpass123"
        )
        self.book = Book.objects.create(
            google_book_id="test_book_001",
            title="Test Book Title",
            authors="Test Author",
            description="A test book description",
            pagecount="250"
        )
        self.book2 = Book.objects.create(
            google_book_id="test_book_002",
            title="Second Test Book",
            authors="Another Author",
            description="Another test book",
            pagecount="300"
        )

    def test_create_valid_wishlist_entry(self):
        """Test creating a valid wishlist entry"""
        wishlist = Wishlist.objects.create(
            user=self.user,
            book=self.book
        )

        self.assertIsNotNone(wishlist.pk)
        self.assertEqual(wishlist.user, self.user)
        self.assertEqual(wishlist.book, self.book)
        self.assertIsNotNone(wishlist.wished_datetime)
        self.assertIsNone(wishlist.removed_datetime)

    def test_wished_datetime_auto_set(self):
        """Test that wished_datetime is automatically set on creation"""
        before_creation = timezone.now()
        wishlist = Wishlist.objects.create(user=self.user, book=self.book)
        after_creation = timezone.now()

        self.assertGreaterEqual(wishlist.wished_datetime, before_creation)
        self.assertLessEqual(wishlist.wished_datetime, after_creation)

    def test_removed_datetime_none_on_creation(self):
        """Test that removed_datetime is None when wishlist entry is created"""
        wishlist = Wishlist.objects.create(user=self.user, book=self.book)

        self.assertIsNone(wishlist.removed_datetime)

    def test_user_cannot_wish_for_owned_book(self):
        """Test that user cannot add book they own to wishlist (CRITICAL validation)"""
        UserBook.objects.create(user=self.user, book=self.book)

        wishlist = Wishlist(user=self.user, book=self.book)

        with self.assertRaises(ValidationError) as context:
            wishlist.clean()

        self.assertIn("already owned by the wisher", str(context.exception))

    def test_user_cannot_wish_for_borrowed_book(self):
        """Test that user cannot wish for book they are currently borrowing"""
        UserBook.objects.create(user=self.user, book=self.book)

        # self.user2 borrows book from self.user
        Transaction.objects.create(
            owner=self.user,
            borrower=self.user2,
            book=self.book
        )

        # self.user2 tries to add borrowed book to wishlist
        wishlist = Wishlist(user=self.user2, book=self.book)

        with self.assertRaises(ValidationError) as context:
            wishlist.clean()

        self.assertIn("already borrowed by the wisher", str(context.exception))

    def test_user_can_wish_after_returning_book(self):
        """Test that user can wish for book after returning it"""
        UserBook.objects.create(user=self.user, book=self.book)

        # self.user2 borrows and returns book
        transaction = Transaction.objects.create(
            owner=self.user,
            borrower=self.user2,
            book=self.book
        )
        transaction.returned_datetime = timezone.now()
        transaction.save()

        # Now self.user2 can add it to wishlist
        wishlist = Wishlist.objects.create(user=self.user2, book=self.book)

        self.assertIsNotNone(wishlist.pk)

    def test_unique_together_user_book(self):
        """Test that user+book combination is unique in wishlist"""
        Wishlist.objects.create(user=self.user, book=self.book)

        # Try to create duplicate
        with self.assertRaises(IntegrityError):
            Wishlist.objects.create(user=self.user, book=self.book)

    def test_set_removed_datetime(self):
        """Test setting removed_datetime when wish is fulfilled"""
        wishlist = Wishlist.objects.create(user=self.user, book=self.book)

        self.assertIsNone(wishlist.removed_datetime)

        # Mark as removed
        removal_time = timezone.now()
        wishlist.removed_datetime = removal_time
        wishlist.save()

        wishlist.refresh_from_db()
        self.assertEqual(wishlist.removed_datetime, removal_time)

    def test_wishlist_str_representation(self):
        """Test __str__ representation of wishlist entry"""
        wishlist = Wishlist.objects.create(user=self.user, book=self.book)

        str_repr = str(wishlist)
        self.assertIn(self.user.username, str_repr)
        self.assertIn(self.book.title, str_repr)

    def test_query_active_wishes(self):
        """Test querying for active (non-removed) wishlist entries"""
        # Create 2 wishlist entries, remove 1
        wish1 = Wishlist.objects.create(user=self.user, book=self.book)
        wish1.removed_datetime = timezone.now()
        wish1.save()

        wish2 = Wishlist.objects.create(user=self.user, book=self.book2)

        # Query active wishes
        active_wishes = Wishlist.objects.filter(removed_datetime__isnull=True)

        self.assertEqual(active_wishes.count(), 1)
        self.assertIn(wish2, active_wishes)
        self.assertNotIn(wish1, active_wishes)

    def test_wishlist_foreign_key_cascade(self):
        """Test that deleting user cascades to delete wishlist entries"""
        wishlist = Wishlist.objects.create(user=self.user, book=self.book)
        wishlist_id = wishlist.pk

        self.user.delete()

        self.assertFalse(Wishlist.objects.filter(pk=wishlist_id).exists())

    def test_signal_updates_wishlist_on_transaction(self):
        """Test that creating transaction updates wishlist (signal test)"""
        UserBook.objects.create(user=self.user, book=self.book)

        # self.user2 adds book to wishlist
        wishlist = Wishlist.objects.create(user=self.user2, book=self.book)
        self.assertIsNone(wishlist.removed_datetime)

        # self.user2 borrows the book (triggers signal)
        Transaction.objects.create(
            owner=self.user,
            borrower=self.user2,
            book=self.book
        )

        # Wishlist should be auto-updated
        wishlist.refresh_from_db()
        self.assertIsNotNone(wishlist.removed_datetime)

    def test_signal_updates_wishlist_on_ownership(self):
        """Test that adding book ownership updates wishlist (signal test)"""
        # self.user adds book to wishlist
        wishlist = Wishlist.objects.create(user=self.user, book=self.book)
        self.assertIsNone(wishlist.removed_datetime)

        # self.user acquires the book (triggers signal)
        UserBook.objects.create(user=self.user, book=self.book)

        # Wishlist should be auto-updated
        wishlist.refresh_from_db()
        self.assertIsNotNone(wishlist.removed_datetime)

    def test_multiple_users_can_wish_same_book(self):
        """Test that multiple users can wish for the same book"""
        wish1 = Wishlist.objects.create(user=self.user, book=self.book)
        wish2 = Wishlist.objects.create(user=self.user2, book=self.book)

        self.assertNotEqual(wish1.pk, wish2.pk)
        self.assertEqual(Wishlist.objects.filter(book=self.book).count(), 2)
