"""Forms for the news app — currently just the registration form."""

from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import CustomUser


class RegistrationForm(UserCreationForm):
    """Sign-up form that also asks the user what role they want.

    Editors are deliberately not selectable here — editor accounts
    are created by superusers in the admin to prevent self-promotion.
    """

    # Only let new users sign up as reader or journalist.
    SIGNUP_ROLES = [
        (CustomUser.Role.READER, "Reader"),
        (CustomUser.Role.JOURNALIST, "Journalist"),
        (CustomUser.Role.EDITOR, "Editor"),
    ]

    role = forms.ChoiceField(
        choices=SIGNUP_ROLES,
        widget=forms.RadioSelect,
        label="Sign up as",
    )
    email = forms.EmailField(required=True)

    class Meta:
        model = CustomUser
        fields = ("username", "email", "role", "password1", "password2")

    def save(self, commit=True):
        """Save the user with their chosen role.

        UserCreationForm.save() returns a user with no role yet, so
        we set it before saving. CustomUser.save() then handles
        group assignment automatically.
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.role = self.cleaned_data["role"]
        if commit:
            user.save()
        return user
