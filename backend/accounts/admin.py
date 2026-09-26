from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from accounts.models import ApiToken, User


class AccountUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "display_name")

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            email = email.strip().lower()
        return email


class AccountUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = (
            "email",
            "display_name",
            "password",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
            "browser_profile_id",
            "browser_profile_status",
            "browser_profile_error",
            "stripe_provision_error",
        )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            email = email.strip().lower()
        return email


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = AccountUserChangeForm
    add_form = AccountUserCreationForm
    ordering = ("email",)
    list_display = ("email", "display_name", "is_staff", "browser_profile_status")
    search_fields = ("email", "display_name")
    readonly_fields = ("date_joined", "last_login")
    filter_horizontal = ("groups", "user_permissions")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("display_name",)}),
        (
            "Provisioning",
            {
                "fields": (
                    "browser_profile_id",
                    "browser_profile_status",
                    "browser_profile_error",
                    "stripe_provision_error",
                )
            },
        ),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "display_name", "password1", "password2"),
            },
        ),
    )


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at")
    readonly_fields = ("key", "created_at")
    search_fields = ("user__email",)
