from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    UpdateView,
)

from .forms import AirDuctCalibrationForm, GardenForm, TroughForm, WitherBatchForm
from .models import (
    AirDuctCalibration,
    Garden,
    Trough,
    WitherBatch,
    has_valid_calibration,
    valid_calibration,
)


def _wants_htmx(request):
    return request.headers.get("HX-Request") == "true"


def gardens_with_valid_calibration():
    """持有有效风道标定的茶园列表（首页计数与列表筛选共用同一判定）。"""
    return [g for g in Garden.objects.all() if has_valid_calibration(g)]


@login_required
def home(request):
    valid_gardens = gardens_with_valid_calibration()
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
        "valid_garden_count": len(valid_gardens),
    }
    return render(request, "home.html", context)


# ---- Garden ----


class GardenListView(LoginRequiredMixin, ListView):
    model = Garden
    template_name = "gardens/list.html"
    context_object_name = "gardens"

    def get_queryset(self):
        gardens = list(Garden.objects.all())
        self.valid_map = {g.pk: valid_calibration(g) for g in gardens}
        if self.request.GET.get("valid") == "1":
            gardens = [g for g in gardens if self.valid_map[g.pk] is not None]
        return gardens

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if _wants_htmx(request):
            html = render_to_string(
                "gardens/_table.html",
                {
                    "gardens": self.object_list,
                    "valid_map": self.valid_map,
                    "valid_filter": request.GET.get("valid") == "1",
                },
                request=request,
            )
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["valid_map"] = getattr(self, "valid_map", {})
        context["valid_filter"] = self.request.GET.get("valid") == "1"
        return context


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


# ---- AirDuctCalibration ----


class CalibrationListView(LoginRequiredMixin, ListView):
    model = AirDuctCalibration
    template_name = "calibrations/list.html"
    context_object_name = "calibrations"

    def get_queryset(self):
        qs = AirDuctCalibration.objects.select_related("garden", "recordedBy")
        garden_id = self.request.GET.get("garden")
        if garden_id:
            qs = qs.filter(garden_id=garden_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["gardens"] = Garden.objects.all()
        context["selected_garden"] = self.request.GET.get("garden", "")
        return context

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if _wants_htmx(request):
            html = render_to_string(
                "calibrations/_table.html",
                {"calibrations": self.object_list},
                request=request,
            )
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)


class CalibrationCreateView(LoginRequiredMixin, CreateView):
    """萎凋工（普通登录用户）即可建票。"""

    model = AirDuctCalibration
    form_class = AirDuctCalibrationForm
    template_name = "calibrations/form.html"
    success_url = reverse_lazy("calibration_list")

    def form_valid(self, form):
        form.instance.recordedBy = self.request.user
        messages.success(self.request, "风道标定票已创建")
        return super().form_valid(form)


class CalibrationDeleteView(UserPassesTestMixin, DeleteView):
    """作废票仅主管（is_staff）可执行，其余用户一律 403 拒绝。"""

    model = AirDuctCalibration
    template_name = "calibrations/confirm_delete.html"
    success_url = reverse_lazy("calibration_list")
    raise_exception = True

    def test_func(self):
        return self.request.user.is_staff

    def form_valid(self, form):
        messages.success(self.request, "风道标定票已作废")
        return super().form_valid(form)
