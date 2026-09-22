from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from inspection.models import ArchiveHit, Inspection, QueryArchive
from inspection.rules import judge

VERDICT_CHOICES = ["", "合格", "不合格"]


def _can_write(user) -> bool:
    return user.groups.filter(name="inspector").exists()


def _search(note_keyword: str, verdict: str):
    qs = Inspection.objects.all()
    if note_keyword:
        qs = qs.filter(note__contains=note_keyword)
    if verdict:
        qs = qs.filter(verdict=verdict)
    return qs.order_by("id")


def health(_request):
    from django.http import JsonResponse

    return JsonResponse({"status": "ok", "service": "nav-aid-inspection"})


@require_http_methods(["GET", "POST"])
def login_view(request):
    from django.contrib.auth import authenticate, login

    error = ""
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username", "").strip(),
            password=request.POST.get("password", ""),
        )
        if user is None:
            error = "用户名或密码错误"
        else:
            login(request, user)
            return redirect("list")
    return render(request, "login.html", {"error": error})


def logout_view(request):
    from django.contrib.auth import logout

    logout(request)
    return redirect("login")


@login_required
def list_view(request):
    rows = Inspection.objects.all()
    return render(request, "list.html", {"rows": rows, "can_write": _can_write(request.user)})


@login_required
def detail_view(request, pk):
    row = get_object_or_404(Inspection, pk=pk)
    return render(request, "detail.html", {"row": row})


@login_required
@require_http_methods(["GET", "POST"])
def create_view(request):
    if not _can_write(request.user):
        return HttpResponseForbidden("仅巡检员可登记灯光巡检")
    error = ""
    if request.method == "POST":
        try:
            measured = float(request.POST["measured_cd"])
            required = float(request.POST["required_cd"])
            bearing = float(request.POST["bearing_error_deg"])
            code = request.POST["aid_code"].strip()
            if not code:
                raise ValueError("empty")
        except (KeyError, ValueError):
            error = "请填编号和三项数值"
        else:
            verdict, note = judge(measured, required, bearing)
            row = Inspection.objects.create(
                aid_code=code,
                measured_cd=measured,
                required_cd=required,
                bearing_error_deg=bearing,
                verdict=verdict,
                note=note,
                created_by=request.user.username,
            )
            return redirect("detail", pk=row.pk)
    return render(request, "form.html", {"error": error})


@login_required
@require_http_methods(["GET", "POST"])
def note_edit_view(request, pk):
    if not _can_write(request.user):
        return HttpResponseForbidden("仅巡检员可修改附言")
    row = get_object_or_404(Inspection, pk=pk)
    if request.method == "POST":
        note = request.POST.get("note", "").strip()
        if note:
            row.note = note[:200]
            row.save(update_fields=["note"])
        return redirect("detail", pk=row.pk)
    return render(request, "note_form.html", {"row": row})


@login_required
def search_view(request):
    """按附言里的字、再配合判词一起查。"""
    keyword = request.GET.get("q", "").strip()
    verdict = request.GET.get("verdict", "").strip()
    if verdict not in VERDICT_CHOICES:
        verdict = ""
    results = []
    searched = bool(request.GET) and bool(keyword)
    if searched:
        results = list(_search(keyword, verdict))
    return render(
        request,
        "search.html",
        {
            "keyword": keyword,
            "verdict": verdict,
            "results": results,
            "searched": searched,
            "no_match": searched and not results,
        },
    )


@login_required
@require_http_methods(["POST"])
def archive_save_view(request):
    """把这次命中存下来供以后核对；持灯与只读都能保存。"""
    keyword = request.POST.get("q", "").strip()
    verdict = request.POST.get("verdict", "").strip()
    if verdict not in VERDICT_CHOICES:
        verdict = ""
    if not keyword:
        return redirect("search")
    hits = list(_search(keyword, verdict))
    archive = QueryArchive.objects.create(
        note_keyword=keyword,
        verdict=verdict,
        saved_by=request.user.username,
    )
    ArchiveHit.objects.bulk_create(
        [
            ArchiveHit(archive=archive, inspection=row, note_snapshot=row.note)
            for row in hits
        ]
    )
    return redirect("archive_detail", pk=archive.pk)


@login_required
def archive_list_view(request):
    archives = QueryArchive.objects.all()
    return render(request, "archive_list.html", {"archives": archives})


@login_required
def archive_detail_view(request, pk):
    """存档主键与此刻重新查询的主键并排；附言被改过的行标成过期。"""
    archive = get_object_or_404(QueryArchive, pk=pk)
    current = {row.id: row for row in _search(archive.note_keyword, archive.verdict)}

    stale_ids = archive.stale_hit_ids()
    archived = []
    for hit in archive.hits.select_related("inspection").order_by("id"):
        archived.append(
            {
                "inspection_id": hit.inspection_id,
                "note_snapshot": hit.note_snapshot,
                "stale": hit.inspection_id in stale_ids,
                "still_matches": hit.inspection_id in current,
            }
        )
    archived_ids = {item["inspection_id"] for item in archived}
    current_rows = [
        {
            "inspection_id": row_id,
            "note": row.note,
            "new": row_id not in archived_ids,
            "stale": row_id in stale_ids,
        }
        for row_id, row in sorted(current.items())
    ]
    return render(
        request,
        "archive_detail.html",
        {
            "archive": archive,
            "archived": archived,
            "current_rows": current_rows,
            "archived_ids": archived_ids,
            "has_diff": bool(stale_ids)
            or any(row["new"] for row in current_rows)
            or any(not item["still_matches"] for item in archived),
        },
    )
