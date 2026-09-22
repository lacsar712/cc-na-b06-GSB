from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from inspection.models import Inspection, SearchArchive
from inspection.rules import judge

VERDICT_CHOICES = ["合格", "不合格"]


def _can_write(user) -> bool:
    return user.groups.filter(name="inspector").exists()


def _query_inspections(keyword: str, verdict: str):
    """按附言查询字 + 判词条件组合查询。"""
    qs = Inspection.objects.all()
    if keyword:
        qs = qs.filter(note__contains=keyword)
    if verdict:
        qs = qs.filter(verdict=verdict)
    return qs


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
def edit_note_view(request, pk):
    """只改附言；判词保持不变。仅持灯（巡检员）可操作。"""
    if not _can_write(request.user):
        return HttpResponseForbidden("仅巡检员可修改附言")
    row = get_object_or_404(Inspection, pk=pk)
    if request.method == "POST":
        note = request.POST.get("note", "").strip()
        if not note:
            return render(
                request,
                "note_form.html",
                {"row": row, "error": "附言不能为空"},
            )
        row.note = note[:200]
        row.save(update_fields=["note"])
        return redirect("detail", pk=row.pk)
    return render(request, "note_form.html", {"row": row})


@login_required
@require_http_methods(["GET", "POST"])
def search_view(request):
    """附言查询字 + 判词组合查询；持灯与只读都能把命中存成存档。"""
    if request.method == "POST":
        keyword = request.POST.get("keyword", "").strip()
        verdict = request.POST.get("verdict", "").strip()
        if not keyword:
            return render(
                request,
                "search.html",
                {
                    "error": "请输入附言查询字",
                    "keyword": keyword,
                    "verdict": verdict,
                    "verdicts": VERDICT_CHOICES,
                },
            )
        rows = _query_inspections(keyword, verdict)
        archive = SearchArchive.objects.create(
            keyword=keyword,
            verdict=verdict,
            hits={str(r.pk): {"note": r.note, "verdict": r.verdict} for r in rows},
            created_by=request.user.username,
        )
        return redirect("archive_detail", pk=archive.pk)

    keyword = request.GET.get("keyword", "").strip()
    verdict = request.GET.get("verdict", "").strip()
    searched = request.GET.get("q") == "1"
    error = ""
    rows = []
    if searched:
        if not keyword:
            error = "请输入附言查询字"
        else:
            rows = list(_query_inspections(keyword, verdict))
    return render(
        request,
        "search.html",
        {
            "rows": rows,
            "searched": searched,
            "no_match": searched and bool(keyword) and not rows,
            "error": error,
            "keyword": keyword,
            "verdict": verdict,
            "verdicts": VERDICT_CHOICES,
        },
    )


@login_required
def archive_list_view(request):
    archives = SearchArchive.objects.all()
    return render(request, "archives.html", {"archives": archives})


@login_required
def archive_detail_view(request, pk):
    """并排核对：存档里的主键集合 vs 此刻按相同条件重新查询的主键集合。"""
    archive = get_object_or_404(SearchArchive, pk=pk)
    archived_pks = archive.hit_pks()
    current_rows = list(_query_inspections(archive.keyword, archive.verdict))
    current_pks = {r.pk for r in current_rows}
    archived_objs = Inspection.objects.in_bulk(archived_pks)

    comparison = []
    for pk in sorted(archived_pks):
        old_note = archive.snap_note(pk)
        old_verdict = archive.snap_verdict(pk)
        obj = archived_objs.get(pk)
        if obj is None:
            status, reason, current_note, current_verdict = "过期", "记录已删除", "—", "—"
        elif obj.note != old_note:
            status, reason, current_note, current_verdict = (
                "过期",
                "附言已改",
                obj.note,
                obj.verdict,
            )
        elif obj.verdict != old_verdict:
            status, reason, current_note, current_verdict = (
                "过期",
                "判词已变",
                obj.note,
                obj.verdict,
            )
        elif pk not in current_pks:
            status, reason, current_note, current_verdict = (
                "过期",
                "已不在查询结果",
                obj.note,
                obj.verdict,
            )
        else:
            status, reason, current_note, current_verdict = (
                "仍命中",
                "",
                obj.note,
                obj.verdict,
            )
        comparison.append(
            {
                "pk": pk,
                "aid_code": obj.aid_code if obj else "—",
                "archived_note": old_note,
                "archived_verdict": old_verdict,
                "current_note": current_note,
                "current_verdict": current_verdict,
                "status": status,
                "reason": reason,
            }
        )

    new_rows = [r for r in current_rows if r.pk not in archived_pks]
    return render(
        request,
        "archive_detail.html",
        {
            "archive": archive,
            "comparison": comparison,
            "new_rows": new_rows,
            "archived_count": len(archived_pks),
            "current_count": len(current_pks),
            "stale_count": sum(1 for c in comparison if c["status"] == "过期"),
        },
    )
