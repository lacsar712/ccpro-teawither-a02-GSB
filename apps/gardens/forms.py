from django import forms

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
    class Meta:
        model = AirDuctCalibration
        fields = ["garden", "calibrationDate", "windSpeed", "passed"]
        widgets = {
            "garden": forms.Select(attrs={"class": "input"}),
            "calibrationDate": forms.DateInput(
                attrs={"class": "input", "type": "date"}
            ),
            "windSpeed": forms.NumberInput(
                attrs={"class": "input", "step": "0.01", "min": "0"}
            ),
            "passed": forms.CheckboxInput(),
        }

    def clean_windSpeed(self):
        value = self.cleaned_data.get("windSpeed")
        if value is not None and value <= 0:
            raise forms.ValidationError("风速读数必须为正数。")
        return value

    def clean(self):
        cleaned_data = super().clean()
        garden = cleaned_data.get("garden")
        calibration_date = cleaned_data.get("calibrationDate")
        if garden and calibration_date:
            duplicate = AirDuctCalibration.objects.filter(
                garden=garden, calibrationDate=calibration_date
            ).first()
            if duplicate and duplicate.pk != (self.instance.pk if self.instance else None):
                raise forms.ValidationError(
                    f"该园此自然日已有标定票：{duplicate.ticket_label()}，不得重复建票。"
                )
        return cleaned_data
