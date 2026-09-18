import json

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.models import User
from apps.reports.models import Category, Report
from apps.reports.services import ReportWorkflow

from .decorators import authority_required
from .forms import AssignReportForm, AuthorityLoginForm, VerifyReportForm


@require_http_methods(["GET", "POST"])
def dashboard_login(request):
    if request.user.is_authenticated and (
        request.user.is_superuser or request.user.role == User.Role.AUTHORITY
    ):
        return redirect("authority-dashboard:overview")

    form = AuthorityLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
        )
        if user is None:
            messages.error(request, "Invalid email or password.")
        elif not (user.is_superuser or user.role == User.Role.AUTHORITY):
            messages.error(request, "This account does not have authority access.")
        else:
            login(request, user)
            return redirect(request.GET.get("next") or "authority-dashboard:overview")
    return render(request, "dashboard/login.html", {"form": form})


@require_POST
def dashboard_logout(request):
    logout(request)
    return redirect("authority-dashboard:login")


@authority_required
def overview(request):
    reports = Report.objects.all()
    status_counts = {status: reports.filter(status=status).count() for status, _ in Report.Status.choices}
    category_counts = list(
        Category.objects.annotate(report_count=Count("reports"))
        .filter(report_count__gt=0)
        .order_by("-report_count", "name")[:8]
    )
    recent_reports = reports.select_related("citizen", "category", "assigned_worker")[:8]
    context = {
        "total_reports": reports.count(),
        "open_reports": reports.exclude(status__in=[Report.Status.RESOLVED, Report.Status.REJECTED]).count(),
        "resolved_reports": status_counts.get(Report.Status.RESOLVED, 0),
        "active_workers": User.objects.filter(role=User.Role.WORKER, is_active=True).count(),
        "citizens": User.objects.filter(role=User.Role.CITIZEN, is_active=True).count(),
        "status_counts": status_counts,
        "category_counts": category_counts,
        "recent_reports": recent_reports,
    }
    return render(request, "dashboard/overview.html", context)


@authority_required
def reports_list(request):
    qs = Report.objects.select_related("citizen", "category", "assigned_worker")
    status = request.GET.get("status", "").strip()
    category = request.GET.get("category", "").strip()
    worker = request.GET.get("worker", "").strip()
    search = request.GET.get("q", "").strip()

    if status:
        qs = qs.filter(status=status)
    if category:
        qs = qs.filter(category_id=category)
    if worker:
        qs = qs.filter(assigned_worker_id=worker)
    if search:
        qs = qs.filter(
            Q(description__icontains=search)
            | Q(address__icontains=search)
            | Q(citizen__email__icontains=search)
            | Q(citizen__first_name__icontains=search)
            | Q(citizen__last_name__icontains=search)
        )

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))
    context = {
        "page": page,
        "statuses": Report.Status.choices,
        "categories": Category.objects.filter(is_active=True).order_by("sort_order", "name"),
        "workers": User.objects.filter(role=User.Role.WORKER, is_active=True).order_by("email"),
        "filters": {"status": status, "category": category, "worker": worker, "q": search},
    }
    return render(request, "dashboard/reports_list.html", context)


@authority_required
def report_detail(request, report_id):
    report = get_object_or_404(
        Report.objects.select_related("citizen", "category", "assigned_worker", "verified_by")
        .prefetch_related("images", "status_history__changed_by"),
        pk=report_id,
    )
    context = {
        "report": report,
        "verify_form": VerifyReportForm(),
        "assign_form": AssignReportForm(),
    }
    return render(request, "dashboard/report_detail.html", context)


@authority_required
@require_POST
def verify_report(request, report_id):
    form = VerifyReportForm(request.POST)
    if form.is_valid():
        try:
            ReportWorkflow.verify(report_id, request.user, form.cleaned_data["note"])
            messages.success(request, "Report verified successfully.")
        except Exception as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Could not verify the report. Please check the form.")
    return redirect("authority-dashboard:report-detail", report_id=report_id)


@authority_required
@require_POST
def assign_report(request, report_id):
    form = AssignReportForm(request.POST)
    if form.is_valid():
        try:
            ReportWorkflow.assign(
                report_id,
                request.user,
                form.cleaned_data["worker"],
                form.cleaned_data["note"],
            )
            messages.success(request, "Worker assigned successfully.")
        except Exception as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Choose a valid active worker.")
    return redirect("authority-dashboard:report-detail", report_id=report_id)


@authority_required
def workers_list(request):
    workers = (
        User.objects.filter(role=User.Role.WORKER)
        .annotate(
            assigned_count=Count(
                "assigned_reports",
                filter=Q(assigned_reports__status__in=[Report.Status.ASSIGNED, Report.Status.IN_PROGRESS]),
            ),
            resolved_count=Count(
                "assigned_reports",
                filter=Q(assigned_reports__status=Report.Status.RESOLVED),
            ),
        )
        .order_by("-is_active", "email")
    )
    return render(request, "dashboard/workers_list.html", {"workers": workers})


@authority_required
def report_map(request):
    reports = Report.objects.select_related("category", "assigned_worker").exclude(location__isnull=True)
    status = request.GET.get("status", "").strip()
    if status:
        reports = reports.filter(status=status)

    points = []
    for report in reports[:500]:
        points.append(
            {
                "id": str(report.id),
                "lat": report.location.y,
                "lng": report.location.x,
                "status": report.status,
                "category": report.category.name,
                "description": report.description[:140],
                "url": f"/authority/reports/{report.id}/",
            }
        )
    return render(
        request,
        "dashboard/map.html",
        {"points_json": json.dumps(points), "statuses": Report.Status.choices, "selected_status": status},
    )
