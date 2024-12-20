"""
URL configuration for bookswap project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings  # Required for debug toolbar
from django.urls import path, include
from books.views import (
    index,
    LoggedInPage,
    LoggedOutPage,
    SignUp,
    CreateGroup,
    JoinGroup,
    LeaveGroup,
    UserAccount,
    book_search,
    RequestsToUserAll,
    RequestsToUserSingle,
    book_database,
    book_database_wishes,
    group_database,
    SingleBook,
    SingleGroup,
    AddToLibraryWishView,
    AddToLibraryConfirmView,
    AddToWishListConfirmView,
    RequestRaisedView,
    RequestDecisionView,
)

# Django provides login and logout views so we dont create them in views.py
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", index, name="index"),
    path(
        "login", auth_views.LoginView.as_view(template_name="login.html"), name="login"
    ),
    path("logout", auth_views.LogoutView.as_view(), name="logout"),
    path("loggedin", LoggedInPage.as_view(), name="loggedin"),
    path("loggedout", LoggedOutPage.as_view(), name="loggedout"),
    path("signup", SignUp.as_view(), name="signup"),
    path("create_group", CreateGroup.as_view(), name="create_group"),
    path("join_group/<slug>/", JoinGroup.as_view(), name="join_group"),
    path("leave_group/<slug>/", LeaveGroup.as_view(), name="leave_group"),
    path("user/<str:pk>/", UserAccount.as_view(), name="user_account"),
    path("book_search/", book_search, name="book_search"),
    path(
        "requests_to_user_all/",
        RequestsToUserAll.as_view(),
        name="requests_to_user_all",
    ),
    path(
        "requests_to_user_single/<str:pk>/",
        RequestsToUserSingle.as_view(),
        name="requests_to_user_single",
    ),
    # path("my_loan_requests/", MyLoanRequests.as_view(), name="my_loan_requests"),
    path("books/", book_database, name="book_database"),
    path("books/<str:pk>/", SingleBook.as_view(), name="single_book"),
    path("wanted/", book_database_wishes, name="book_database_wishes"),
    path("groups/", group_database, name="group_database"),
    path("groups/<str:slug>/", SingleGroup.as_view(), name="single_group"),
    path("add-to-library/", AddToLibraryWishView.as_view(), name="add_to_library"),
    path(
        "add-to-library/confirm/",
        AddToLibraryConfirmView.as_view(),
        name="add_to_library_confirm",
    ),
    path(
        "add-to-wishlist/confirm/",
        AddToWishListConfirmView.as_view(),
        name="add_to_wishlist_confirm",
    ),
    path(
        "request_raised/",
        RequestRaisedView.as_view(),
        name="request_raised",
    ),
    path(
        "request_decision/",
        RequestDecisionView.as_view(),
        name="request_decision",
    ),
]

# Required for debug toolbar
if settings.DEBUG:
    import debug_toolbar

    SHOW_TOOLBAR_CALLBACK = True
    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]
