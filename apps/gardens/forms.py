from django import forms
from django.utils import timezone

from .models import AirDuctCalibration, Garden, Trough, WitherBatch


class GardenForm(forms.ModelForm):
    class Meta:
        model = Garden
        fields = ["name", "altitudeBand", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input"}),
            "altitudeBand": forms.TextInput(attrs={"class": "input"}),
            "notes": forms.Textarea(attrs={"class": "input", "rows": 3}),
        }


class TroughForm(forms.ModelForm):
    class Meta:
        model = Trough
        fields = ["garden", "troughCode", "cultivar", "loadKg", "status"]
        widgets = {
            "garden": forms.Select(attrs={"class": "input"}),
            "troughCode": forms.TextInput(attrs={"class": "input"}),
            "cultivar": forms.TextInput(attrs={"class": "input"}),
            "loadKg": forms.NumberInput(attrs={"class": "input", "step": "0.01"}),
            "status": forms.Select(attrs={"class": "input"}),
        }


class WitherBatchForm(forms.ModelForm):
    class Meta:
        model = WitherBatch
        fields = [
            "trough",
            "startedAt",
            "targetMoisture",
            "actualMoisture",
            "rollGrade",
        ]
        widgets = {
            "trough": forms.Select(attrs={"class": "input"}),
            "startedAt": forms.DateTimeInput(
                attrs={"class": "input", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "targetMoisture": forms.NumberInput(
                attrs={"class": "input", "step": "0.01"}
            ),
            "actualMoisture": forms.NumberInput(
                attrs={"class": "input", "step": "0.01"}
            ),
            "rollGrade": forms.TextInput(attrs={"class": "input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["startedAt"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        if self.instance and self.instance.pk and self.instance.startedAt:
            from django.utils import timezone

            local = timezone.localtime(self.instance.startedAt)
            self.initial["startedAt"] = local.strftime("%Y-%m-%dT%H:%M")


class AirDuctCalibrationForm(forms.ModelForm):
    """风道标定票表单：记录人由视图自动取当前登录用户。"""

    # ModelForm 的 BooleanField 默认 required=True（不勾选即报错），
    # 必须显式 required=False，否则无法录入「未通过」票
    passed = forms.BooleanField(
        label="是否通过", required=False, widget=forms.CheckboxInput()
    )

    class Meta:
        model = AirDuctCalibration
        fields = ["garden", "calibrationDate", "windSpeed", "passed"]
        widgets = {
            "garden": forms.Select(attrs={"class": "input"}),
            "calibrationDate": forms.DateInput(
                attrs={"class": "input", "type": "date"},
                format="%Y-%m-%d",
            ),
            "windSpeed": forms.NumberInput(
                attrs={"class": "input", "step": "0.01", "min": "0.01"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["calibrationDate"].input_formats = ["%Y-%m-%d"]
        if not (self.instance and self.instance.pk):
            self.fields["calibrationDate"].initial = timezone.localdate()
