from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    AirDuctCalibration,
    Garden,
    Trough,
    garden_has_valid_calibration,
)


def make_user(username, superuser=False):
    User = get_user_model()
    if superuser:
        return User.objects.create_superuser(
            username, f"{username}@test.local", "pass123456"
        )
    return User.objects.create_user(
        username, f"{username}@test.local", "pass123456"
    )


class CalibrationRuleTests(TestCase):
    """风道标定票规则与槽位改态校验（模型层）。"""

    def setUp(self):
        self.admin = make_user("admin", superuser=True)
        self.worker = make_user("witherer")
        self.garden = Garden.objects.create(name="一号园", altitudeBand="800m")
        self.today = timezone.localdate()

    def ticket(self, garden=None, days_ago=0, passed=True, wind="2.00", voided=False):
        return AirDuctCalibration.objects.create(
            garden=garden or self.garden,
            calibrationDate=self.today - timedelta(days=days_ago),
            windSpeed=Decimal(wind),
            passed=passed,
            recorder=self.worker,
            isVoided=voided,
        )

    def loading_trough(self, garden=None, code="A-01"):
        return Trough.objects.create(
            garden=garden or self.garden,
            troughCode=code,
            cultivar="福鼎大白",
            loadKg=Decimal("100.00"),
            status=Trough.STATUS_LOADING,
        )

    # ---- 票字段校验 ----

    def test_wind_speed_zero_rejected(self):
        with self.assertRaises(ValidationError):
            self.ticket(wind="0")

    def test_wind_speed_negative_rejected(self):
        with self.assertRaises(ValidationError):
            self.ticket(wind="-0.50")

    def test_duplicate_day_rejected_and_echoes_existing_ticket(self):
        first = self.ticket()
        with self.assertRaises(ValidationError) as ctx:
            self.ticket()
        self.assertIn(f"#{first.pk}", str(ctx.exception))
        self.assertEqual(AirDuctCalibration.objects.count(), 1)

    # ---- 有效标定判定（共用函数）----

    def test_recent_passed_ticket_is_valid(self):
        self.ticket(days_ago=7)  # 恰好七天前仍有效（不早于七个自然日前）
        self.assertTrue(garden_has_valid_calibration(self.garden))

    def test_expired_ticket_is_invalid(self):
        self.ticket(days_ago=8)
        self.assertFalse(garden_has_valid_calibration(self.garden))

    def test_failed_ticket_is_invalid(self):
        self.ticket(passed=False)
        self.assertFalse(garden_has_valid_calibration(self.garden))

    def test_voided_ticket_is_invalid(self):
        self.ticket(voided=True)
        self.assertFalse(garden_has_valid_calibration(self.garden))

    def test_failed_ticket_does_not_replace_older_valid_pass(self):
        self.ticket(days_ago=3, passed=True)
        self.ticket(days_ago=1, passed=False)
        self.assertTrue(garden_has_valid_calibration(self.garden))

    # ---- 装叶中 → 萎凋中 改态校验 ----

    def test_loading_to_withering_blocked_without_calibration(self):
        trough = self.loading_trough()
        trough.status = Trough.STATUS_WITHERING
        with self.assertRaises(ValidationError) as ctx:
            trough.save()
        self.assertIn("有效风道标定", str(ctx.exception))
        trough.refresh_from_db()
        self.assertEqual(trough.status, Trough.STATUS_LOADING)

    def test_loading_to_withering_blocked_when_ticket_failed(self):
        self.ticket(passed=False)
        trough = self.loading_trough()
        trough.status = Trough.STATUS_WITHERING
        with self.assertRaises(ValidationError):
            trough.save()

    def test_loading_to_withering_allowed_with_valid_calibration(self):
        self.ticket(days_ago=2)
        trough = self.loading_trough()
        trough.status = Trough.STATUS_WITHERING
        trough.save()
        trough.refresh_from_db()
        self.assertEqual(trough.status, Trough.STATUS_WITHERING)

    def test_staying_withering_does_not_require_calibration(self):
        self.ticket(days_ago=1)
        trough = self.loading_trough()
        trough.status = Trough.STATUS_WITHERING
        trough.save()
        AirDuctCalibration.objects.all().update(isVoided=True)
        trough.loadKg = Decimal("120.00")
        trough.save()  # 保持「萎凋中」的编辑不再要求标定
        self.assertEqual(
            Trough.objects.get(pk=trough.pk).status, Trough.STATUS_WITHERING
        )


class CalibrationViewTests(TestCase):
    """建票权限、作废权限、首页统计与茶园列表筛选一致性。"""

    def setUp(self):
        self.admin = make_user("admin", superuser=True)
        self.worker = make_user("witherer")
        self.g1 = Garden.objects.create(name="有效园", altitudeBand="800m")
        self.g2 = Garden.objects.create(name="无效园", altitudeBand="600m")
        self.today = timezone.localdate()
        AirDuctCalibration.objects.create(
            garden=self.g1,
            calibrationDate=self.today,
            windSpeed=Decimal("2.50"),
            passed=True,
            recorder=self.worker,
        )

    def test_home_valid_garden_count_matches_filtered_list(self):
        self.client.force_login(self.worker)
        home = self.client.get(reverse("home"))
        self.assertEqual(home.context["valid_garden_count"], 1)

        filtered = self.client.get(reverse("garden_list") + "?valid=1")
        self.assertEqual(len(filtered.context["gardens"]), 1)
        self.assertEqual(filtered.context["gardens"][0].name, "有效园")

        unfiltered = self.client.get(reverse("garden_list"))
        self.assertEqual(len(unfiltered.context["gardens"]), 2)

    def test_withering_worker_can_create_ticket(self):
        self.client.force_login(self.worker)
        resp = self.client.post(
            reverse("calibration_create"),
            {
                "garden": self.g2.pk,
                "calibrationDate": self.today.isoformat(),
                "windSpeed": "1.80",
                "passed": "on",
            },
        )
        self.assertRedirects(resp, reverse("calibration_list"))
        ticket = AirDuctCalibration.objects.get(garden=self.g2)
        self.assertEqual(ticket.recorder, self.worker)
        self.assertTrue(ticket.passed)

    def test_can_create_failed_ticket_via_form(self):
        # 未勾选「是否通过」也应能正常建票（未通过票同样要录入）
        self.client.force_login(self.worker)
        resp = self.client.post(
            reverse("calibration_create"),
            {
                "garden": self.g2.pk,
                "calibrationDate": self.today.isoformat(),
                "windSpeed": "0.60",
            },
        )
        self.assertRedirects(resp, reverse("calibration_list"))
        ticket = AirDuctCalibration.objects.get(garden=self.g2)
        self.assertFalse(ticket.passed)
        self.assertFalse(garden_has_valid_calibration(self.g2))

    def test_duplicate_day_via_form_echoes_existing_ticket(self):
        self.client.force_login(self.worker)
        existing = AirDuctCalibration.objects.get(garden=self.g1)
        resp = self.client.post(
            reverse("calibration_create"),
            {
                "garden": self.g1.pk,
                "calibrationDate": self.today.isoformat(),
                "windSpeed": "1.80",
                "passed": "on",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f"#{existing.pk}")
        self.assertEqual(
            AirDuctCalibration.objects.filter(garden=self.g1).count(), 1
        )

    def test_worker_cannot_void_ticket(self):
        ticket = AirDuctCalibration.objects.get(garden=self.g1)
        self.client.force_login(self.worker)
        resp = self.client.post(reverse("calibration_void", args=[ticket.pk]))
        self.assertRedirects(resp, reverse("calibration_list"))
        ticket.refresh_from_db()
        self.assertFalse(ticket.isVoided)

    def test_supervisor_can_void_ticket(self):
        ticket = AirDuctCalibration.objects.get(garden=self.g1)
        self.client.force_login(self.admin)
        resp = self.client.post(reverse("calibration_void", args=[ticket.pk]))
        self.assertRedirects(resp, reverse("calibration_list"))
        ticket.refresh_from_db()
        self.assertTrue(ticket.isVoided)
        self.assertFalse(garden_has_valid_calibration(self.g1))

    def test_trough_edit_view_blocks_withering_without_calibration(self):
        trough = Trough.objects.create(
            garden=self.g2,
            troughCode="B-01",
            cultivar="黄金芽",
            loadKg=Decimal("80.00"),
            status=Trough.STATUS_LOADING,
        )
        self.client.force_login(self.worker)
        resp = self.client.post(
            reverse("trough_edit", args=[trough.pk]),
            {
                "garden": self.g2.pk,
                "troughCode": "B-01",
                "cultivar": "黄金芽",
                "loadKg": "80.00",
                "status": Trough.STATUS_WITHERING,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "有效风道标定")
        trough.refresh_from_db()
        self.assertEqual(trough.status, Trough.STATUS_LOADING)
