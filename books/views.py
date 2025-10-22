from django.conf import settings  # To pull in env variables
from django.shortcuts import render
from django.http import Http404
from django.db.models import Count, Q
import logging

logger = logging.getLogger(__name__)
from django.views.generic import (
    CreateView,
    TemplateView,
    DetailView,
    RedirectView,
    UpdateView,
    ListView,
    View,
)
from .forms import UserCreateForm, RequestStatusForm
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
import requests
from requests.exceptions import RequestException
from json.decoder import JSONDecodeError
from django.utils import timezone
from datetime import timedelta
from django.utils.dateparse import parse_datetime
from .models import (
    Book,
    CustomUser,
    Group,
    GroupMember,
    UserBook,
    Wishlist,
    RequestBook,
)
from django.contrib.auth.mixins import LoginRequiredMixin
import os
from django.shortcuts import redirect


def index(request):
    return render(request, "index.html")


class SignUp(CreateView):
    form_class = UserCreateForm
    template_name = "signup.html"
    # Successful signup to login page. Reverse_lazy waits for submit button
    success_url = reverse_lazy("login")
    success_message = "Account created successfully. You can now log in!"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return response


class CreateGroup(LoginRequiredMixin, CreateView):
    model = Group
    fields = ("group_name", "description", "is_private")
    success_url = reverse_lazy("group_database")


class JoinGroup(LoginRequiredMixin, RedirectView):

    # Once action is performed, where should they go
    def get_redirect_url(self, *args, **kwargs):
        # Get group 'slug' of page user is clicking into and go to group page
        return reverse("single_group", kwargs={"slug": self.kwargs.get("slug")})

    # Check if user can perform action
    def get(self, request, *args, **kwargs):
        group = get_object_or_404(Group, slug=self.kwargs.get("slug"))
        GroupMember.objects.create(user=self.request.user, group=group)
        return super().get(request, *args, **kwargs)


class LeaveGroup(LoginRequiredMixin, RedirectView):

    # Once action is performed, where should they go
    def get_redirect_url(self, *args, **kwargs):
        # Get group 'slug' of page user is clicking into and go to group page
        return reverse("single_group", kwargs={"slug": self.kwargs.get("slug")})

    # Check if user can perform action
    def get(self, request, *args, **kwargs):
        membership = GroupMember.objects.filter(
            user=self.request.user, group__slug=self.kwargs.get("slug")
        ).get()
        membership.delete()
        return super().get(request, *args, **kwargs)


# TODO: Turn these into ListView. Paigination
def book_database(request):
    books_list = Book.objects.filter(owner__isnull=False).order_by("title").distinct()
    books_dict = {"books": books_list}
    return render(request, "book_database.html", context=books_dict)


def book_database_wishes(request):
    # Query to count distinct users wishing for each book
    books_list = (
        Book.objects.filter(
            book_wish__user__isnull=False,  # Filter to include only books that are wished for
            book_wish__removed_datetime__isnull=True,  # Book is still wanted and hasn't been removed
        )
        .annotate(
            wishers_count=Count(
                "book_wish__user", distinct=True
            ),  # Count distinct users wishing for the book
            owners_count=Count(
                "book_owners__user", distinct=True
            ),  # Count distinct users owning the book
        )
        .order_by("title")
    )  # Order by book title
    books_dict = {"books": books_list}
    return render(request, "book_database_wishlist.html", context=books_dict)


def group_database(request):
    groups_list = Group.objects.order_by("group_name")
    groups_dict = {"groups": groups_list}
    return render(request, "group_database.html", context=groups_dict)


class UserAccount(TemplateView):
    template_name = "account_details.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_pk = self.kwargs["pk"]  # obtain elements from URL
        user_username = get_object_or_404(CustomUser, id=user_pk)

        # Query the user's books
        user_books = Book.objects.filter(owner=user_pk).order_by("title")
        user_book_count = UserBook.objects.filter(user=user_pk).count()

        # Query the user's book wishes
        # TODO: Put this in reusable function with the one in SingleBook
        user_wish = Wishlist.objects.filter(
            user=user_pk, removed_datetime__isnull=True
        ).annotate(owners_count=Count("book__owner", filter=~Q(book__owner=user_pk)))

        # user_wish = Wishlist.objects.filter(user=user_pk, removed_datetime__isnull=True)
        user_wish_count = Wishlist.objects.filter(
            user=user_pk, removed_datetime__isnull=True
        ).count()

        # Query the number of groups the user belongs to
        user_groups = Group.objects.filter(members=user_pk).order_by("group_name")
        user_group_count = GroupMember.objects.filter(user=user_pk).count()

        # Query the number of requests the user has made. Open and Closed
        user_requests_open = RequestBook.objects.filter(
            requester=user_pk, decision_datetime__isnull=True
        ).order_by("request_datetime")

        # Query the number of requests the user has recieved. Open and Closed
        user_requests_recieved_open = RequestBook.objects.filter(
            owner=user_pk, decision_datetime__isnull=True
        ).order_by("request_datetime")

        # Add the data to the context
        context["user_username"] = user_username
        context["user_books"] = user_books
        context["user_book_count"] = user_book_count
        context["user_wish"] = user_wish
        context["user_wish_count"] = user_wish_count
        context["user_groups"] = user_groups
        context["user_group_count"] = user_group_count
        context["user_requests_open_count"] = user_requests_open.count()
        context[
            "user_requests_recieved_open_count"
        ] = user_requests_recieved_open.count()

        return context


class LoggedInPage(TemplateView):
    template_name = "loggedin.html"


class LoggedOutPage(TemplateView):
    template_name = "loggedout.html"


class SingleBook(DetailView):
    model = Book
    template_name = "book_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        book = self.get_object()
        owners = book.book_owners.all()

        book_pk = self.kwargs["pk"]  # obtain elements from URL
        # TODO: Put this in reusable function with the one in UserAccount
        user_wish = Wishlist.objects.filter(book=book_pk, removed_datetime__isnull=True)
        user_wish_count = Wishlist.objects.filter(
            book=book_pk, removed_datetime__isnull=True
        ).count()

        # Only check for certain things if user is logged in
        if self.request.user.is_authenticated:
            user = self.request.user

            # Check if logged in user owns the book
            is_owner = owners.filter(user=user).exists()

            # If user requested the book, extract list of owners
            user_requests = RequestBook.objects.filter(
                book=book, requester=user, decision_datetime__isnull=True
            )
            requested_owner_usernames = user_requests.values_list(
                "owner__username", flat=True
            )
        else:
            requested_owner_usernames = []
            is_owner = False

        context["owners"] = owners
        context["is_owner"] = is_owner
        context["user_wish"] = user_wish
        context["user_wish_count"] = user_wish_count
        context["requested_owner_usernames"] = requested_owner_usernames
        return context


class SingleGroup(DetailView):
    model = Group
    template_name = "group_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        group = self.get_object()
        members = group.group_memberships.all()
        context["members"] = members
        return context


def get_book_section(item, section):
    return item.get(section, {})


def process_book_item(item):

    # Pull back individual json sections of the selected book
    id_google = get_book_section(item, "id")
    book_info = get_book_section(item, "volumeInfo")

    title = book_info.get("title", "N/A")
    authors = ", ".join(book_info.get("authors", ["N/A"]))
    thumbnail = book_info.get("imageLinks", {}).get("thumbnail", "")
    description = book_info.get("description", "N/A")
    pageCount = book_info.get("pageCount", "N/A")
    identifiers = book_info.get("industryIdentifiers", "N/A")

    # Use dictionary to store identifiers - cleaner than multiple variables
    identifier_map = {
        "ISBN_13": "N/A",
        "ISBN_10": "N/A",
        "OTHER": "N/A",
    }

    # Only process identifiers if it's a list (not "N/A" string)
    if isinstance(identifiers, list):
        for i in identifiers:
            try:
                id_type = i.get("type")
                id_value = i.get("identifier")
                if id_type in identifier_map and id_value:
                    identifier_map[id_type] = id_value
            except (AttributeError, TypeError) as e:
                logger.warning("Invalid identifier format in book data: %s", e)
                continue

    return {
        "id_google": id_google,
        "title": title,
        "authors": authors,
        "thumbnail": thumbnail,
        "description": description,
        "pageCount": pageCount,
        "ID_ISBN_13": identifier_map["ISBN_13"],
        "ID_ISBN_10": identifier_map["ISBN_10"],
        "ID_OTHER": identifier_map["OTHER"],
    }


def book_search(request):

    if request.method == "POST":
        query = request.POST.get("query")

        if query:
            try:
                # Google Books API URL
                url = f"https://www.googleapis.com/books/v1/volumes?q={query}&key={settings.GOOGLE_BOOKS_API_KEY}"

                # Make a request to the API
                response = requests.get(url)
                response.raise_for_status()  # Raise error for bad responses

                # Parse the JSON response
                data = response.json()

                # Pull back ALL json sections of the selected book
                data_items = get_book_section(data, "items")

                # Extract relevant information
                books = [process_book_item(item) for item in data_items]

                # Render the search results
                return render(
                    request, "book_search.html", {"books": books, "query": query}
                )

            except RequestException as e:
                # Handle request-related exceptions
                return render(
                    request,
                    "book_search.html",
                    {"error_message": f"Error making API request: {e}"},
                )

            except JSONDecodeError as e:
                # Handle JSON decoding error
                return render(
                    request,
                    "book_search.html",
                    {"error_message": f"Error decoding JSON response: {e}"},
                )

    return render(request, "book_search.html")


class AddToLibraryWishView(View):
    # Expected POST parameters for cleaner extraction
    BOOK_PARAMS = [
        "action", "id_google", "title", "authors", "thumbnail",
        "description", "pageCount", "ID_ISBN_13", "ID_ISBN_10", "ID_OTHER"
    ]

    # Action handler registry for clean dispatch pattern
    def _add_to_library(self, user, book):
        """Add book to user's library"""
        user.book_set.add(book)

    def _add_to_wishlist(self, user, book):
        """Add book to user's wishlist"""
        Wishlist.objects.get_or_create(user=user, book=book)

    # Map actions to (handler_method, redirect_url)
    ACTION_HANDLERS = {
        "add_to_library": (_add_to_library, "add_to_library_confirm"),
        "add_to_wishlist": (_add_to_wishlist, "add_to_wishlist_confirm"),
    }

    def post(self, request, *args, **kwargs):
        user = request.user

        # Extract all POST parameters using registry pattern
        params = {key: request.POST.get(key) for key in self.BOOK_PARAMS}

        if params["id_google"] and params["title"]:
            logger.debug("Adding or retrieving existing book with ID: %s", params["id_google"])
            try:
                book, created = Book.objects.get_or_create(
                    google_book_id=params["id_google"],
                    defaults={
                        "title": params["title"],
                        "authors": params["authors"],
                        "thumbnail": params["thumbnail"],
                        "description": params["description"],
                        "pagecount": params["pageCount"],
                        "ID_ISBN_13": params["ID_ISBN_13"],
                        "ID_ISBN_10": params["ID_ISBN_10"],
                        "ID_OTHER": params["ID_OTHER"],
                    },
                )
                logger.debug("Book: %s, Created: %s", book.title, created)

                # Use action handler registry for clean dispatch
                handler_info = self.ACTION_HANDLERS.get(params["action"])
                if handler_info:
                    handler_method, redirect_url = handler_info
                    handler_method(self, user, book)
                    return redirect(redirect_url)
                else:
                    logger.warning("Invalid action received: %s", params["action"])
                    messages.error(request, "Invalid action")
                    return redirect("book_search")

            except (IntegrityError, ValidationError) as e:
                logger.error("Error adding book to library/wishlist: %s", str(e), exc_info=True)
                messages.error(request, f"Unable to add book: {str(e)}")
                return redirect("book_search")
            except Exception as e:
                # Catch any other unexpected errors
                logger.error("Unexpected error adding book: %s", str(e), exc_info=True)
                messages.error(request, "An unexpected error occurred. Please try again.")
                return redirect("book_search")


class AddToLibraryConfirmView(TemplateView):
    template_name = "add_to_library_confirm.html"


class AddToWishListConfirmView(TemplateView):
    template_name = "add_to_wishlist_confirm.html"


class RequestRaisedView(LoginRequiredMixin, UpdateView):
    def post(self, request, *args, **kwargs):
        requester_id = request.POST.get("requester")
        owner_id = request.POST.get("owner")
        google_book_id = request.POST.get("google_book_id")
        if requester_id and owner_id and google_book_id:
            RequestBook.objects.create(
                requester=CustomUser.objects.get(pk=requester_id),
                owner=CustomUser.objects.get(pk=owner_id),
                book=Book.objects.get(pk=google_book_id),
            )
            return HttpResponseRedirect(
                reverse("single_book", kwargs={"pk": google_book_id})
            )


class RequestsToUserAll(LoginRequiredMixin, ListView):
    model = RequestBook
    template_name = "requests_to_user_all.html"
    context_object_name = "requests_to_user_all"
    # paginate_by = 2

    # Registry pattern for request status filters - eliminates code duplication
    REQUEST_STATUS_FILTERS = {
        "open": {"decision_datetime__isnull": True},
        "accept": {"decision_datetime__isnull": False, "decision": True},
        "reject": {"decision_datetime__isnull": False, "decision": False},
    }

    # Filter handler registry for clean dispatch
    @property
    def FILTER_HANDLERS(self):
        return {
            "owner": self.get_requests_by_owner,
            "requester": self.get_requests_by_requester,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get the current logged-in user
        user = self.request.user

        # Get the filter parameter from the URL
        filter_by = self.request.GET.get("filter_by")

        # Pass value to context to HTML page can use it for dynamic changes to common page
        context["filter_by"] = filter_by

        # Use filter handler registry for clean dispatch
        handler = self.FILTER_HANDLERS.get(filter_by)
        if handler:
            logger.debug("Filtering requests by %s: %s", filter_by, user.username)
            context = handler(user, context)
        else:
            raise Http404("Filter parameter is not valid.")

        return context

    def _get_requests_by_status(self, user, role_field):
        """DRY helper to get requests by status (open/accept/reject).

        Args:
            user: The user to filter by
            role_field: Either "owner" or "requester"

        Returns:
            Dict with keys: requests_to_user_open, requests_to_user_accept, requests_to_user_reject
        """
        result = {}
        for status_key, filters in self.REQUEST_STATUS_FILTERS.items():
            query_filters = {role_field: user, **filters}
            result[f"requests_to_user_{status_key}"] = RequestBook.objects.filter(
                **query_filters
            ).order_by("-request_datetime")
        return result

    def get_requests_by_owner(self, user, context):
        """Books requested FROM the user. User IS the owner of the book and is giving them away"""
        context.update(self._get_requests_by_status(user, "owner"))
        return context

    def get_requests_by_requester(self, user, context):
        """Books requested BY the user. User is not the owner of the book and wants to borrow it"""
        context.update(self._get_requests_by_status(user, "requester"))
        return context


class RequestsToUserSingle(LoginRequiredMixin, DetailView):
    model = RequestBook
    template_name = "requests_to_user_single.html"


class RequestDecisionView(LoginRequiredMixin, UpdateView):
    # Decision mapping for cleaner logic
    DECISION_MAP = {"Approve": True, "Reject": False}

    def post(self, request, *args, **kwargs):
        time_window = timedelta(seconds=1)  # Calculate a small time window for matching
        decisionInput = request.POST.get("decision")
        requester_id = request.POST.get("requester")
        owner_id = request.POST.get("owner")
        google_book_id = request.POST.get("google_book_id")
        reject_reason = request.POST.get("reject_reason")  # Will be blank for approve
        request_datetime = parse_datetime(request.POST.get("request_datetime"))
        if decisionInput and requester_id and owner_id and google_book_id:
            request_book = RequestBook.objects.get(
                requester=CustomUser.objects.get(pk=requester_id),
                owner=CustomUser.objects.get(pk=owner_id),
                book=Book.objects.get(pk=google_book_id),
                request_datetime__gte=request_datetime - time_window,
                request_datetime__lte=request_datetime + time_window,
            )
            # Use decision map for cleaner conditional logic
            request_book.decision = self.DECISION_MAP.get(decisionInput)
            request_book.reject_reason = reject_reason
            request_book.decision_datetime = timezone.now()
            request_book.save()
            return HttpResponseRedirect(
                reverse("requests_to_user_all") + "?filter_by=owner"
            )
