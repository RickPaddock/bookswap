from django.shortcuts import render
from django.views.generic import CreateView, TemplateView, DetailView
from .forms import UserCreateForm
from django.contrib import messages
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404
import requests
from requests.exceptions import RequestException
from json.decoder import JSONDecodeError
from .models import Book, Group, GroupMember, UserBook, Wishlist
from django.contrib.auth.mixins import LoginRequiredMixin
import os


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


# Testing a list of a model: Return books with owners
def book_database(request):
    books_list = Book.objects.filter(owner__isnull=False).order_by("title").distinct()
    books_dict = {"books": books_list}
    return render(request, "book_database.html", context=books_dict)


def group_database(request):
    groups_list = Group.objects.order_by("group_name")
    groups_dict = {"groups": groups_list}
    return render(request, "group_database.html", context=groups_dict)


class UserAccount(LoginRequiredMixin, TemplateView):
    template_name = "account_details.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Query the user's books
        user_books = Book.objects.filter(owner=user).order_by("title")
        user_book_count = UserBook.objects.filter(user=user).count()

        # Query the user's book wishes
        user_wish = Wishlist.objects.filter(user=user)
        user_wish_count = Wishlist.objects.filter(user=user).count()

        # Query the number of groups the user belongs to
        user_groups = Group.objects.filter(members=user).order_by("group_name")
        user_group_count = GroupMember.objects.filter(user=user).count()

        # Add the data to the context
        context["user_books"] = user_books
        context["user_book_count"] = user_book_count
        context["user_wish"] = user_wish
        context["user_wish_count"] = user_wish_count
        context["user_groups"] = user_groups
        context["user_group_count"] = user_group_count
        # Add other model-related data as needed

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
        context["owners"] = owners
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


from django.views.generic import View
from django.shortcuts import redirect
from .models import CustomUser, Book


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
                )  # Redirect back to user account page if ISBN or title is not provided or if book creation fails


class AddToLibraryConfirmView(TemplateView):
    template_name = "add_to_library_confirm.html"


class AddToWishListConfirmView(TemplateView):
    template_name = "add_to_wishlist_confirm.html"
