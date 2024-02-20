from django.shortcuts import render
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
from django.http import HttpResponseRedirect
import requests
from requests.exceptions import RequestException
from json.decoder import JSONDecodeError
from django.utils import timezone
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
        user_wish = Wishlist.objects.filter(user=user_pk)
        user_wish_count = Wishlist.objects.filter(user=user_pk).count()

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
        user_wish = Wishlist.objects.filter(book=book_pk)
        user_wish_count = Wishlist.objects.filter(book=book_pk).count()

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

    ID_ISBN_13 = "N/A"
    ID_ISBN_10 = "N/A"
    ID_OTHER = "N/A"

    for i in identifiers:
        try:
            if i["type"] == "ISBN_13":
                ID_ISBN_13 = i["identifier"]
            if i["type"] == "ISBN_10":
                ID_ISBN_10 = i["identifier"]
            if i["type"] == "OTHER":
                ID_OTHER = i["identifier"]
        except:
            pass

    return {
        "id_google": id_google,
        "title": title,
        "authors": authors,
        "thumbnail": thumbnail,
        "description": description,
        "pageCount": pageCount,
        "ID_ISBN_13": ID_ISBN_13,
        "ID_ISBN_10": ID_ISBN_10,
        "ID_OTHER": ID_OTHER,
    }


def book_search(request):

    GOOGLE_BOOKS_API_KEY = "AIzaSyBVAeqv6x8nytkSb_Mn4pXfza3nLUp8a0I"

    if request.method == "POST":
        query = request.POST.get("query")

        if query:
            try:
                # Google Books API URL
                url = f"https://www.googleapis.com/books/v1/volumes?q={query}&key={GOOGLE_BOOKS_API_KEY}"

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
    def post(self, request, *args, **kwargs):
        user = request.user
        action = request.POST.get("action")
        id_google = request.POST.get("id_google")
        title = request.POST.get("title")
        authors = request.POST.get("authors")
        thumbnail = request.POST.get("thumbnail")
        description = request.POST.get("description")
        pageCount = request.POST.get("pageCount")
        ID_ISBN_13 = request.POST.get("ID_ISBN_13")
        ID_ISBN_10 = request.POST.get("ID_ISBN_10")
        ID_OTHER = request.POST.get("ID_OTHER")

        if id_google and title:
            try:
                book, created = Book.objects.get_or_create(
                    google_book_id=id_google,
                    title=title,
                    authors=authors,
                    thumbnail=thumbnail,
                    description=description,
                    pagecount=pageCount,
                    ID_ISBN_13=ID_ISBN_13,
                    ID_ISBN_10=ID_ISBN_10,
                    ID_OTHER=ID_OTHER,
                )
                if action == "add_to_library":
                    user.book_set.add(book)
                    return redirect(
                        "add_to_library_confirm"
                    )  # Redirect to a confirmation page
                elif action == "add_to_wishlist":
                    Wishlist.objects.get_or_create(user=user, book=book)
                    return redirect(
                        "add_to_wishlist_confirm"
                    )  # Redirect to a confirmation page

            except Exception as e:
                print("Exception!", str(e))
                return redirect(
                    "user_account"
                )  # Redirect back to user account if book creation fails


class AddToLibraryConfirmView(TemplateView):
    template_name = "add_to_library_confirm.html"


class AddToWishListConfirmView(TemplateView):
    template_name = "add_to_wishlist_confirm.html"


# TODO: If a user has requested the book before, the request button doesnt disable in the single_book page when pressed
class RequestRaisedView(LoginRequiredMixin, UpdateView):
    def post(self, request, *args, **kwargs):
        requester_id = request.POST.get("requester")
        owner_id = request.POST.get("owner")
        google_book_id = request.POST.get("google_book_id")
        if requester_id and owner_id and google_book_id:
            RequestBook.objects.get_or_create(
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get the current logged-in user
        user = self.request.user

        # Filter RequestBook objects where the current user is the requester
        requests_to_user_open = RequestBook.objects.filter(
            owner=user, decision_datetime__isnull=True
        ).order_by("-request_datetime")
        requests_to_user_accept = RequestBook.objects.filter(
            owner=user, decision_datetime__isnull=False, decision=True
        ).order_by("-request_datetime")
        requests_to_user_reject = RequestBook.objects.filter(
            owner=user, decision_datetime__isnull=False, decision=False
        ).order_by("-request_datetime")

        context["requests_to_user_open"] = requests_to_user_open
        context["requests_to_user_accept"] = requests_to_user_accept
        context["requests_to_user_reject"] = requests_to_user_reject
        return context


class RequestsToUserSingle(LoginRequiredMixin, DetailView):
    model = RequestBook
    template_name = "requests_to_user_single.html"


# TODO: combine these into one view
class RequestApproveView(LoginRequiredMixin, UpdateView):
    def post(self, request, *args, **kwargs):
        requester_id = request.POST.get("requester")
        owner_id = request.POST.get("owner")
        google_book_id = request.POST.get("google_book_id")
        if requester_id and owner_id and google_book_id:
            request_book = RequestBook.objects.get(
                requester=CustomUser.objects.get(pk=requester_id),
                owner=CustomUser.objects.get(pk=owner_id),
                book=Book.objects.get(pk=google_book_id),
            )
            request_book.decision = True
            request_book.decision_datetime = timezone.now()
            request_book.save()
            return HttpResponseRedirect(reverse("requests_to_user_all"))


class RequestRejectView(LoginRequiredMixin, UpdateView):
    def post(self, request, *args, **kwargs):
        requester_id = request.POST.get("requester")
        owner_id = request.POST.get("owner")
        google_book_id = request.POST.get("google_book_id")
        reject_reason = request.POST.get("reject_reason")
        if requester_id and owner_id and google_book_id:
            request_book = RequestBook.objects.get(
                requester=CustomUser.objects.get(pk=requester_id),
                owner=CustomUser.objects.get(pk=owner_id),
                book=Book.objects.get(pk=google_book_id),
            )
            request_book.decision = False
            request_book.decision_datetime = timezone.now()
            request_book.reject_reason = reject_reason
            request_book.save()
            return HttpResponseRedirect(reverse("requests_to_user_all"))
