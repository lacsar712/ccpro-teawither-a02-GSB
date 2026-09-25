# Generated manually for TeaWither A02 (air duct calibration ticket)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gardens", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AirDuctCalibration",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("calibrationDate", models.DateField(verbose_name="标定日")),
                (
                    "windSpeed",
                    models.DecimalField(
                        decimal_places=2, max_digits=6, verbose_name="风速读数(m/s)"
                    ),
                ),
                ("passed", models.BooleanField(verbose_name="是否通过")),
                ("isVoided", models.BooleanField(default=False, verbose_name="已作废")),
                (
                    "createdAt",
                    models.DateTimeField(auto_now_add=True, verbose_name="创建时间"),
                ),
                (
                    "garden",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="calibrations",
                        to="gardens.garden",
                        verbose_name="所属茶园",
                    ),
                ),
                (
                    "recorder",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="calibrations",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="记录人",
                    ),
                ),
            ],
            options={
                "verbose_name": "风道标定票",
                "verbose_name_plural": "风道标定票",
                "ordering": ["-calibrationDate", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="airductcalibration",
            constraint=models.UniqueConstraint(
                fields=("garden", "calibrationDate"),
                name="uniq_calibration_per_garden_day",
            ),
        ),
    ]
