import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

# 风道标定通过票的有效天数：标定日不得早于七个自然日前。
CALIBRATION_VALID_DAYS = 7


class Garden(models.Model):
    name = models.CharField("茶园名称", max_length=120)
    altitudeBand = models.CharField("海拔带", max_length=60)
    notes = models.TextField("备注", blank=True, default="")

    class Meta:
        ordering = ["name"]
        verbose_name = "茶园"
        verbose_name_plural = "茶园"

    def __str__(self):
        return self.name

    def latest_calibration(self, on_date=None):
        return latest_calibration(self, on_date)

    def valid_calibration(self, on_date=None):
        return valid_calibration(self, on_date)

    def has_valid_calibration(self, on_date=None):
        return has_valid_calibration(self, on_date)


class Trough(models.Model):
    STATUS_LOADING = "loading"
    STATUS_WITHERING = "withering"
    STATUS_READY = "ready"
    STATUS_CHOICES = [
        (STATUS_LOADING, "装叶中"),
        (STATUS_WITHERING, "萎凋中"),
        (STATUS_READY, "可下槽"),
    ]

    garden = models.ForeignKey(
        Garden,
        on_delete=models.CASCADE,
        related_name="troughs",
        verbose_name="茶园",
    )
    troughCode = models.CharField("槽位编号", max_length=40)
    cultivar = models.CharField("茶树品种", max_length=80)
    loadKg = models.DecimalField("装叶量(kg)", max_digits=10, decimal_places=2)
    status = models.CharField(
        "状态",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_LOADING,
    )

    class Meta:
        ordering = ["garden__name", "troughCode"]
        verbose_name = "萎凋槽"
        verbose_name_plural = "萎凋槽"
        constraints = [
            models.UniqueConstraint(
                fields=["garden", "troughCode"],
                name="uniq_trough_code_per_garden",
            ),
        ]

    def __str__(self):
        return f"{self.garden.name}-{self.troughCode}"

    def latest_batch(self):
        return self.batches.order_by("-startedAt", "-id").first()

    def clean(self):
        super().clean()
        # 装叶中 -> 萎凋中：该园必须持有有效的风道标定通过票。
        if self.pk and self.status == self.STATUS_WITHERING:
            previous = Trough.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous == self.STATUS_LOADING and not has_valid_calibration(self.garden_id):
                raise ValidationError(
                    {
                        "status": (
                            "缺有效标定：本园最新风道标定票不存在、未通过，"
                            "或标定日早于七个自然日前，槽位不得由装叶中改为萎凋中。"
                        )
                    }
                )
        if self.status != self.STATUS_READY:
            return
        latest = None
        if self.pk:
            latest = (
                WitherBatch.objects.filter(trough_id=self.pk)
                .order_by("-startedAt", "-id")
                .first()
            )
        if latest is None or latest.actualMoisture is None or latest.actualMoisture > 40:
            raise ValidationError(
                {
                    "status": "无法设为可下槽：最新萎凋批次的实测含水率为空或高于 40%。"
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class WitherBatch(models.Model):
    trough = models.ForeignKey(
        Trough,
        on_delete=models.CASCADE,
        related_name="batches",
        verbose_name="萎凋槽",
    )
    startedAt = models.DateTimeField("开始时间")
    targetMoisture = models.DecimalField(
        "目标含水率(%)", max_digits=5, decimal_places=2
    )
    actualMoisture = models.DecimalField(
        "实测含水率(%)",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    rollGrade = models.CharField("揉捻等级", max_length=40)

    class Meta:
        ordering = ["-startedAt", "-id"]
        verbose_name = "萎凋批次"
        verbose_name_plural = "萎凋批次"

    def __str__(self):
        return f"{self.trough} @ {self.startedAt:%Y-%m-%d %H:%M}"


class AirDuctCalibration(models.Model):
    """风道标定票：同园同一自然日仅允许一张。"""

    garden = models.ForeignKey(
        Garden,
        on_delete=models.CASCADE,
        related_name="calibrations",
        verbose_name="所属茶园",
    )
    calibrationDate = models.DateField("标定日")
    windSpeed = models.DecimalField(
        "风速读数", max_digits=8, decimal_places=2
    )
    passed = models.BooleanField("是否通过", default=False)
    recordedBy = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="calibrations",
        verbose_name="记录人",
    )

    class Meta:
        ordering = ["-calibrationDate", "-id"]
        verbose_name = "风道标定票"
        verbose_name_plural = "风道标定票"
        constraints = [
            models.UniqueConstraint(
                fields=["garden", "calibrationDate"],
                name="uniq_calibration_per_garden_day",
            ),
        ]

    def __str__(self):
        result = "通过" if self.passed else "未通过"
        return f"风道标定票 #{self.pk or '-'} {self.garden_id}-{self.calibrationDate:%Y-%m-%d}-{result}"

    def ticket_label(self):
        result = "通过" if self.passed else "未通过"
        return f"#{self.pk}（{self.garden} · {self.calibrationDate:%Y-%m-%d} · {result}）"

    def clean(self):
        super().clean()
        if self.windSpeed is not None and self.windSpeed <= 0:
            raise ValidationError({"windSpeed": "风速读数必须为正数。"})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


def latest_calibration(garden, on_date=None):
    """该园截至 on_date（默认今天）最新一张标定票（含未通过），无票返回 None。"""
    if isinstance(garden, Garden):
        garden_id = garden.pk
    else:
        garden_id = garden
    if on_date is None:
        on_date = timezone.localdate()
    return (
        AirDuctCalibration.objects.filter(garden_id=garden_id, calibrationDate__lte=on_date)
        .order_by("-calibrationDate", "-id")
        .first()
    )


def valid_calibration(garden, on_date=None):
    """该园的有效标定票：最新一张必须通过，且标定日不早于七个自然日前。"""
    if on_date is None:
        on_date = timezone.localdate()
    ticket = latest_calibration(garden, on_date)
    if ticket is None or not ticket.passed:
        return None
    earliest = on_date - datetime.timedelta(days=CALIBRATION_VALID_DAYS)
    if ticket.calibrationDate < earliest:
        return None
    return ticket


def has_valid_calibration(garden, on_date=None):
    """槽位改态与列表/首页筛选共用的有效标定判定。"""
    return valid_calibration(garden, on_date) is not None
