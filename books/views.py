from django.shortcuts import render
from django.views.generic import CreateView, TemplateView
from .forms import UserCreateForm
from django.contrib import messages
from django.urls import reverse_lazy


def index(request):
    return render(request, "index.html")


class SignUp(CreateView):
    form_class = UserCreateForm
    template_name = "signup.html"
    # Upon successful signup go to login page. Reverse_lazy waits for submit button to be pressed
    success_url = reverse_lazy("login")
    success_message = "Your account was created successfully. You can now log in!"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return response


class AccountPage(TemplateView):
    template_name = "account_details.html"


class LoggedInPage(TemplateView):
    template_name = "loggedin.html"


class LoggedOutPage(TemplateView):
    template_name = "loggedout.html"
