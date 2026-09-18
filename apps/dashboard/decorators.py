from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from apps.accounts.models import User


def authority_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect("authority-dashboard:login")
        if user.is_superuser or user.role == User.Role.AUTHORITY:
            return view_func(request, *args, **kwargs)
        messages.error(request, "Authority access is required.")
        return redirect("authority-dashboard:login")

    return wrapped
