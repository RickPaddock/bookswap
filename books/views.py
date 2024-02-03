from django.shortcuts import render
from django.views.generic import CreateView, TemplateView
from .forms import UserCreateForm
from django.contrib import messages
from django.urls import reverse_lazy
import requests
from requests.exceptions import RequestException
from json.decoder import JSONDecodeError
from .models import Book
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


# Testing a list of a model
def book_database(request):
    books_list = Book.objects.order_by("title")
    books_dict = {"books": books_list}
    return render(request, "book_database.html", context=books_dict)


class user_account(TemplateView):
    template_name = "account_details.html"


class LoggedInPage(TemplateView):
    template_name = "loggedin.html"


class LoggedOutPage(TemplateView):
    template_name = "loggedout.html"


def get_book_section(item, section):
    return item.get(section, {})


def process_book_item(item):

    # Pull back individual json sections of the selected book
    id_info = get_book_section(item, "id")
    book_info = get_book_section(item, "volumeInfo")
    ibans = get_book_section(book_info, "industryIdentifiers")

    title = book_info.get("title", "N/A")
    authors = ", ".join(book_info.get("authors", ["N/A"]))
    thumbnail = book_info.get("imageLinks", {}).get("thumbnail", "")
    description = book_info.get("description", "N/A")
    ibans = book_info.get("ibans", "N/A")

    return {
        "id_google": id_info,
        "title": title,
        "authors": authors,
        "thumbnail": thumbnail,
        "description": description,
        "ibans": ibans,
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
