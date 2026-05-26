"""Forms for the news app — currently just the registration form."""

from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import CustomUser


class RegistrationForm(UserCreationForm):
    """Sign-up form that asks the user which role they want.

    All three roles (Reader, Journalist, Editor) are selectable so
    that the application supports all required user personas from
    the front end.
    """

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

    def clean_email(self):
        """Reject sign-ups where the email is already in use.

        The model has a unique constraint on email, so duplicates
        would raise IntegrityError at save time. Catching them here
        surfaces a clean form-level error instead, which renders
        next to the email field in the template.
        """
        email = self.cleaned_data.get("email")
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

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
