"""
Pytest fixtures for BookSwap tests
"""
import pytest
from django.contrib.auth import get_user_model
from books.models import Book, UserBook

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user"""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123"
    )


@pytest.fixture
def user2(db):
    """Create a second test user"""
    return User.objects.create_user(
        username="testuser2",
        email="test2@example.com",
        password="testpass123"
    )


@pytest.fixture
def user3(db):
    """Create a third test user"""
    return User.objects.create_user(
        username="testuser3",
        email="test3@example.com",
        password="testpass123"
    )


@pytest.fixture
def book(db):
    """Create a test book"""
    return Book.objects.create(
        google_book_id="test_book_001",
        title="Test Book Title",
        authors="Test Author",
        description="A test book description",
        pagecount="250"
    )


@pytest.fixture
def book2(db):
    """Create a second test book"""
    return Book.objects.create(
        google_book_id="test_book_002",
        title="Second Test Book",
        authors="Another Author",
        description="Another test book",
        pagecount="300"
    )


@pytest.fixture
def user_book(db, user, book):
    """Create a UserBook relationship (user owns book)"""
    return UserBook.objects.create(user=user, book=book)
