from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


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

    def _is_entering_withering(self):
        """是否正在从非「萎凋中」进入「萎凋中」（新建即萎凋中也视为进入）。"""
        if not self.pk:
            return True
        previous = (
            Trough.objects.filter(pk=self.pk)
            .values_list("status", flat=True)
            .first()
        )
        return previous != self.STATUS_WITHERING

    def clean(self):
        super().clean()
        if self.status == self.STATUS_WITHERING and self._is_entering_withering():
            # 装叶中 → 萎凋中 必须先有有效风道标定，任何保存路径都不得绕过
            if self.garden_id and not garden_has_valid_calibration(self.garden):
                raise ValidationError(
                    {
                        "status": "无法改为「萎凋中」：所属茶园缺少有效风道标定"
                        "（需最新一张通过且未作废的标定票，且标定日不早于七个自然日前）。"
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


# ---- 风道标定 ----

# 有效标定窗口：标定日不早于七个自然日前（含七天前当日）
CALIBRATION_VALID_DAYS = 7


class AirDuctCalibration(models.Model):
    """风道标定票：记录茶园风道风速标定结果，同园同一自然日只允许一张。"""

    garden = models.ForeignKey(
        Garden,
        on_delete=models.CASCADE,
        related_name="calibrations",
        verbose_name="所属茶园",
    )
    calibrationDate = models.DateField("标定日")
    windSpeed = models.DecimalField(
        "风速读数(m/s)", max_digits=6, decimal_places=2
    )
    passed = models.BooleanField("是否通过")
    recorder = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="calibrations",
        verbose_name="记录人",
    )
    isVoided = models.BooleanField("已作废", default=False)
    createdAt = models.DateTimeField("创建时间", auto_now_add=True)

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
        return f"标定票#{self.pk}（{self.garden.name} {self.calibrationDate}）"

    def clean(self):
        super().clean()
        if self.windSpeed is not None and self.windSpeed <= 0:
            raise ValidationError(
                {"windSpeed": "风速读数必须为正数（大于 0）。"}
            )
        if self.garden_id and self.calibrationDate:
            dup = (
                AirDuctCalibration.objects.filter(
                    garden_id=self.garden_id,
                    calibrationDate=self.calibrationDate,
                )
                .exclude(pk=self.pk)
                .first()
            )
            if dup is not None:
                raise ValidationError(
                    {
                        "calibrationDate": f"该茶园 {self.calibrationDate} 已存在"
                        f"标定票 #{dup.pk}，同一自然日只允许一张。"
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


def valid_calibration_qs(on_date=None):
    """有效标定票查询集：通过、未作废、标定日不早于七个自然日前。

    改态校验、首页统计、茶园列表筛选全部由此派生，保证口径一致。
    """
    today = on_date or timezone.localdate()
    cutoff = today - timedelta(days=CALIBRATION_VALID_DAYS)
    return AirDuctCalibration.objects.filter(
        passed=True,
        isVoided=False,
        calibrationDate__gte=cutoff,
    )


def latest_valid_calibration(garden, on_date=None):
    """茶园最新一张有效标定票（通过且未作废、未过期）；无则 None。"""
    return (
        valid_calibration_qs(on_date)
        .filter(garden=garden)
        .order_by("-calibrationDate", "-id")
        .first()
    )


def garden_has_valid_calibration(garden, on_date=None):
    """茶园当前是否存在有效风道标定（槽位改态与此共用同一判定）。"""
    return latest_valid_calibration(garden, on_date) is not None


def valid_calibration_garden_ids(on_date=None):
    """当前具有有效标定的茶园 id 列表（首页统计与列表筛选共用）。"""
    return valid_calibration_qs(on_date).values_list("garden_id", flat=True).distinct()
