from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.db.models import Exists, OuterRef
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    UpdateView,
)

from .forms import (
    AirDuctCalibrationForm,
    GardenForm,
    TroughForm,
    WitherBatchForm,
)
from .models import (
    AirDuctCalibration,
    Garden,
    Trough,
    WitherBatch,
    valid_calibration_garden_ids,
    valid_calibration_qs,
)


def _wants_htmx(request):
    return request.headers.get("HX-Request") == "true"


@login_required
def home(request):
    context = {
        "garden_count": Garden.objects.count(),
        "trough_count": Trough.objects.count(),
        "batch_count": WitherBatch.objects.count(),
        "ready_count": Trough.objects.filter(status=Trough.STATUS_READY).count(),
        "withering_count": Trough.objects.filter(
            status=Trough.STATUS_WITHERING
        ).count(),
        "loading_count": Trough.objects.filter(
            status=Trough.STATUS_LOADING
        ).count(),
        # 与茶园列表 ?valid=1 筛选共用同一有效标定判定，计数必然一致
        "valid_garden_count": Garden.objects.filter(
            pk__in=valid_calibration_garden_ids()
        ).count(),
    }
    return render(request, "home.html", context)


# ---- Garden ----


class GardenListView(LoginRequiredMixin, ListView):
    model = Garden
    template_name = "gardens/list.html"
    context_object_name = "gardens"

    def get_queryset(self):
        # 有效标定判定与首页统计、槽位改态校验共用 valid_calibration_qs
        valid_qs = valid_calibration_qs().filter(garden_id=OuterRef("pk"))
        qs = Garden.objects.annotate(has_valid_calibration=Exists(valid_qs))
        if self.request.GET.get("valid") == "1":
            qs = qs.filter(has_valid_calibration=True)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["valid_only"] = self.request.GET.get("valid") == "1"
        return context

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if _wants_htmx(request):
            html = render_to_string(
                "gardens/_table.html",
                {"gardens": self.object_list},
                request=request,
            )
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)


class GardenCreateView(LoginRequiredMixin, CreateView):
    model = Garden
    form_class = GardenForm
    template_name = "gardens/form.html"
    success_url = reverse_lazy("garden_list")

    def form_valid(self, form):
        messages.success(self.request, "茶园已创建")
        response = super().form_valid(form)
        if _wants_htmx(self.request):
            return redirect("garden_list")
        return response


class GardenUpdateView(LoginRequiredMixin, UpdateView):
    model = Garden
    form_class = GardenForm
    template_name = "gardens/form.html"
    success_url = reverse_lazy("garden_list")

    def form_valid(self, form):
        messages.success(self.request, "茶园已更新")
        return super().form_valid(form)


class GardenDeleteView(LoginRequiredMixin, DeleteView):
    model = Garden
    template_name = "gardens/confirm_delete.html"
    success_url = reverse_lazy("garden_list")

    def form_valid(self, form):
        messages.success(self.request, "茶园已删除")
        return super().form_valid(form)


# ---- Trough ----


class TroughListView(LoginRequiredMixin, ListView):
    model = Trough
    template_name = "troughs/list.html"
    context_object_name = "troughs"

    def get_queryset(self):
        return Trough.objects.select_related("garden").all()

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if _wants_htmx(request):
            html = render_to_string(
                "troughs/_table.html",
                {"troughs": self.object_list},
                request=request,
            )
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)


class TroughCreateView(LoginRequiredMixin, CreateView):
    model = Trough
    form_class = TroughForm
    template_name = "troughs/form.html"
    success_url = reverse_lazy("trough_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋槽已创建")
        return super().form_valid(form)


class TroughUpdateView(LoginRequiredMixin, UpdateView):
    model = Trough
    form_class = TroughForm
    template_name = "troughs/form.html"
    success_url = reverse_lazy("trough_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋槽已更新")
        return super().form_valid(form)


class TroughDeleteView(LoginRequiredMixin, DeleteView):
    model = Trough
    template_name = "troughs/confirm_delete.html"
    success_url = reverse_lazy("trough_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋槽已删除")
        return super().form_valid(form)


# ---- WitherBatch ----


class BatchListView(LoginRequiredMixin, ListView):
    model = WitherBatch
    template_name = "batches/list.html"
    context_object_name = "batches"

    def get_queryset(self):
        return WitherBatch.objects.select_related("trough", "trough__garden").all()

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if _wants_htmx(request):
            html = render_to_string(
                "batches/_table.html",
                {"batches": self.object_list},
                request=request,
            )
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)


class BatchCreateView(LoginRequiredMixin, CreateView):
    model = WitherBatch
    form_class = WitherBatchForm
    template_name = "batches/form.html"
    success_url = reverse_lazy("batch_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋批次已创建")
        return super().form_valid(form)


class BatchUpdateView(LoginRequiredMixin, UpdateView):
    model = WitherBatch
    form_class = WitherBatchForm
    template_name = "batches/form.html"
    success_url = reverse_lazy("batch_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋批次已更新")
        return super().form_valid(form)


class BatchDeleteView(LoginRequiredMixin, DeleteView):
    model = WitherBatch
    template_name = "batches/confirm_delete.html"
    success_url = reverse_lazy("batch_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋批次已删除")
        return super().form_valid(form)


# ---- AirDuctCalibration（风道标定票）----


def _valid_ticket_ids():
    return set(valid_calibration_qs().values_list("pk", flat=True))


class CalibrationListView(LoginRequiredMixin, ListView):
    model = AirDuctCalibration
    template_name = "calibrations/list.html"
    context_object_name = "tickets"

    def get_queryset(self):
        return AirDuctCalibration.objects.select_related("garden", "recorder").all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["valid_ids"] = _valid_ticket_ids()
        return context

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if _wants_htmx(request):
            html = render_to_string(
                "calibrations/_table.html",
                {
                    "tickets": self.object_list,
                    "valid_ids": _valid_ticket_ids(),
                },
                request=request,
            )
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)


class CalibrationCreateView(LoginRequiredMixin, CreateView):
    """萎凋工等登录用户均可建票；记录人自动取当前用户。"""

    model = AirDuctCalibration
    form_class = AirDuctCalibrationForm
    template_name = "calibrations/form.html"
    success_url = reverse_lazy("calibration_list")

    def form_valid(self, form):
        form.instance.recorder = self.request.user
        try:
            response = super().form_valid(form)
        except IntegrityError:
            # 并发兜底：模型 clean 已先行校验，此处防止竞态击穿唯一约束
            existing = AirDuctCalibration.objects.filter(
                garden_id=form.instance.garden_id,
                calibrationDate=form.instance.calibrationDate,
            ).first()
            form.add_error(
                "calibrationDate",
                f"该茶园 {form.instance.calibrationDate} 已存在"
                f"标定票 #{existing.pk}，同一自然日只允许一张。"
                if existing
                else "该茶园当日已存在标定票，同一自然日只允许一张。",
            )
            return self.form_invalid(form)
        messages.success(self.request, "风道标定票已创建")
        return response


class CalibrationVoidView(LoginRequiredMixin, View):
    """作废标定票：仅主管（超级用户）可操作，其余拒绝。"""

    def post(self, request, pk):
        ticket = get_object_or_404(AirDuctCalibration, pk=pk)
        if not request.user.is_superuser:
            messages.error(request, "仅主管可作废标定票，已拒绝本次操作。")
            return redirect("calibration_list")
        if ticket.isVoided:
            messages.info(request, f"标定票 #{ticket.pk} 此前已作废。")
        else:
            ticket.isVoided = True
            ticket.save(update_fields=["isVoided"])
            messages.success(request, f"标定票 #{ticket.pk} 已作废。")
        return redirect("calibration_list")
