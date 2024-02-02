from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    UserCreationForm,
)  # Helps create user accounts. See django documentation

# from django import forms


# Create new user (note name is different to superclass)
class UserCreateForm(UserCreationForm):

    # Fields (from 'django.contrib.auth') user accessess when signing up
    class Meta:
        fields = ("username", "email", "password1", "password2")
        # Get current model of whoever is accessing website
        model = get_user_model()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Labels show on the template
        self.fields["username"].label = "Display Name"
        self.fields["email"].label = "Email Address"
