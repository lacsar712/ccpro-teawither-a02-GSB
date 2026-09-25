from django.contrib import admin

from .models import AirDuctCalibration, Garden, Trough, WitherBatch


@admin.register(Garden)
class GardenAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "altitudeBand")
    search_fields = ("name", "altitudeBand")


@admin.register(Trough)
class TroughAdmin(admin.ModelAdmin):
    list_display = ("id", "garden", "troughCode", "cultivar", "loadKg", "status")
    list_filter = ("status", "garden")
    search_fields = ("troughCode", "cultivar")


@admin.register(WitherBatch)
class WitherBatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "trough",
        "startedAt",
        "targetMoisture",
        "actualMoisture",
        "rollGrade",
    )
    list_filter = ("rollGrade",)


@admin.register(AirDuctCalibration)
class AirDuctCalibrationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "garden",
        "calibrationDate",
        "windSpeed",
        "passed",
        "recorder",
        "isVoided",
    )
    list_filter = ("passed", "isVoided", "garden")
    search_fields = ("garden__name", "recorder__username")
