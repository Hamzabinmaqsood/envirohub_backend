from django import forms

from apps.accounts.models import User


class AuthorityLoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"autofocus": True}))
    password = forms.CharField(widget=forms.PasswordInput)


class VerifyReportForm(forms.Form):
    note = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Verification note (optional)"}),
    )


class AssignReportForm(forms.Form):
    worker = forms.ModelChoiceField(queryset=User.objects.none(), empty_label="Choose worker")
    note = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Assignment note (optional)"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["worker"].queryset = User.objects.filter(
            role=User.Role.WORKER,
            is_active=True,
        ).order_by("first_name", "last_name", "email")
