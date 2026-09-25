import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import AirDuctCalibrationForm
from .models import (
    AirDuctCalibration,
    Garden,
    Trough,
    has_valid_calibration,
    valid_calibration,
)

User = get_user_model()


class CalibrationRuleTests(TestCase):
    def setUp(self):
        self.garden = Garden.objects.create(name="测试园", altitudeBand="600m")
        self.other_garden = Garden.objects.create(name="隔壁园", altitudeBand="800m")
        self.user = User.objects.create_user("witherer", password="123456")
        self.admin = User.objects.create_superuser("admin", password="123456")
        self.today = timezone.localdate()

    def make_ticket(self, garden=None, date=None, wind="3.50", passed=True, user=None):
        return AirDuctCalibration.objects.create(
            garden=garden or self.garden,
            calibrationDate=date or self.today,
            windSpeed=Decimal(wind),
            passed=passed,
            recordedBy=user or self.user,
        )

    # ---- 票字段校验 ----

    def test_wind_speed_must_be_positive_model(self):
        ticket = AirDuctCalibration(
            garden=self.garden,
            calibrationDate=self.today,
            windSpeed=Decimal("0"),
            passed=True,
            recordedBy=self.user,
        )
        with self.assertRaises(ValidationError) as ctx:
            ticket.full_clean()
        self.assertIn("风速读数必须为正数", str(ctx.exception))

    def test_wind_speed_must_be_positive_form(self):
        form = AirDuctCalibrationForm(
            data={
                "garden": self.garden.pk,
                "calibrationDate": self.today.isoformat(),
                "windSpeed": "-1.2",
                "passed": True,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("风速读数必须为正数", form.errors["windSpeed"][0])

    def test_duplicate_same_garden_same_day_rejected_with_ticket_id(self):
        existing = self.make_ticket(wind="2.00")
        form = AirDuctCalibrationForm(
            data={
                "garden": self.garden.pk,
                "calibrationDate": self.today.isoformat(),
                "windSpeed": "4.10",
                "passed": True,
            }
        )
        self.assertFalse(form.is_valid())
        message = str(form.errors)
        self.assertIn("已有标定票", message)
        self.assertIn(f"#{existing.pk}", message)

    def test_same_day_different_garden_allowed(self):
        self.make_ticket(garden=self.garden)
        form = AirDuctCalibrationForm(
            data={
                "garden": self.other_garden.pk,
                "calibrationDate": self.today.isoformat(),
                "windSpeed": "4.10",
                "passed": True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    # ---- 有效标定判定 ----

    def test_passed_ticket_today_is_valid(self):
        self.make_ticket()
        self.assertIsNotNone(valid_calibration(self.garden))
        self.assertTrue(has_valid_calibration(self.garden))

    def test_ticket_seven_days_ago_still_valid(self):
        self.make_ticket(date=self.today - datetime.timedelta(days=7))
        self.assertTrue(has_valid_calibration(self.garden))

    def test_ticket_eight_days_ago_expired(self):
        self.make_ticket(date=self.today - datetime.timedelta(days=8))
        self.assertFalse(has_valid_calibration(self.garden))

    def test_failed_ticket_is_not_valid(self):
        self.make_ticket(passed=False)
        self.assertFalse(has_valid_calibration(self.garden))

    def test_failed_latest_ticket_invalidates_older_pass(self):
        self.make_ticket(date=self.today - datetime.timedelta(days=2), passed=True)
        self.make_ticket(date=self.today, passed=False)
        self.assertFalse(has_valid_calibration(self.garden))

    def test_no_ticket_means_invalid(self):
        self.assertFalse(has_valid_calibration(self.garden))

    # ---- 槽位改态 ----

    def make_loading_trough(self, garden=None):
        return Trough.objects.create(
            garden=garden or self.garden,
            troughCode="T-1",
            cultivar="群体种",
            loadKg=Decimal("50.00"),
            status=Trough.STATUS_LOADING,
        )

    def test_loading_to_withering_blocked_without_calibration(self):
        trough = self.make_loading_trough()
        trough.status = Trough.STATUS_WITHERING
        with self.assertRaises(ValidationError) as ctx:
            trough.full_clean()
        self.assertIn("缺有效标定", str(ctx.exception))

    def test_loading_to_withering_allowed_with_valid_calibration(self):
        self.make_ticket()
        trough = self.make_loading_trough()
        trough.status = Trough.STATUS_WITHERING
        trough.full_clean()
        trough.save()
        trough.refresh_from_db()
        self.assertEqual(trough.status, Trough.STATUS_WITHERING)

    def test_loading_to_withering_blocked_with_failed_ticket(self):
        self.make_ticket(passed=False)
        trough = self.make_loading_trough()
        trough.status = Trough.STATUS_WITHERING
        with self.assertRaises(ValidationError):
            trough.save()

    def test_withering_to_ready_not_affected_by_calibration_rule(self):
        # 无标定但已在萎凋中的槽，改可下槽只受含水率规则约束。
        trough = self.make_loading_trough()
        trough.status = Trough.STATUS_WITHERING
        Trough.objects.filter(pk=trough.pk).update(status=Trough.STATUS_WITHERING)
        trough.status = Trough.STATUS_READY
        # 最新批次缺失 -> 含水率规则拦截（而非标定规则）
        with self.assertRaises(ValidationError) as ctx:
            trough.save()
        self.assertNotIn("缺有效标定", str(ctx.exception))


class CalibrationViewTests(TestCase):
    def setUp(self):
        self.garden = Garden.objects.create(name="视图园", altitudeBand="600m")
        self.user = User.objects.create_user("witherer", password="123456")
        self.admin = User.objects.create_superuser("admin", password="123456")
        self.today = timezone.localdate()

    def ticket_payload(self, garden=None, passed=True):
        return {
            "garden": (garden or self.garden).pk,
            "calibrationDate": self.today.isoformat(),
            "windSpeed": "3.50",
            "passed": "on" if passed else "",
        }

    def test_anonymous_cannot_create(self):
        resp = self.client.get(reverse("calibration_create"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp.url)

    def test_witherer_can_create_ticket(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("calibration_create"), self.ticket_payload(), follow=True
        )
        self.assertEqual(resp.status_code, 200)
        ticket = AirDuctCalibration.objects.get()
        self.assertEqual(ticket.recordedBy, self.user)
        self.assertTrue(ticket.passed)

    def test_witherer_cannot_void_ticket(self):
        ticket = AirDuctCalibration.objects.create(
            garden=self.garden,
            calibrationDate=self.today,
            windSpeed=Decimal("3.5"),
            passed=True,
            recordedBy=self.user,
        )
        self.client.force_login(self.user)
        resp = self.client.post(reverse("calibration_delete", args=[ticket.pk]))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(AirDuctCalibration.objects.filter(pk=ticket.pk).exists())

    def test_supervisor_can_void_ticket(self):
        ticket = AirDuctCalibration.objects.create(
            garden=self.garden,
            calibrationDate=self.today,
            windSpeed=Decimal("3.5"),
            passed=True,
            recordedBy=self.user,
        )
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse("calibration_delete", args=[ticket.pk]), follow=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(AirDuctCalibration.objects.filter(pk=ticket.pk).exists())

    def test_trough_transition_view_blocks_without_valid_calibration(self):
        """禁止改态成功却不查标定：视图层改态同样被拦。"""
        trough = Trough.objects.create(
            garden=self.garden,
            troughCode="V-1",
            cultivar="群体种",
            loadKg=Decimal("50.00"),
            status=Trough.STATUS_LOADING,
        )
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse("trough_edit", args=[trough.pk]),
            {
                "garden": self.garden.pk,
                "troughCode": "V-1",
                "cultivar": "群体种",
                "loadKg": "50.00",
                "status": Trough.STATUS_WITHERING,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "缺有效标定")
        trough.refresh_from_db()
        self.assertEqual(trough.status, Trough.STATUS_LOADING)


class DashboardConsistencyTests(TestCase):
    def setUp(self):
        self.g1 = Garden.objects.create(name="有效园", altitudeBand="600m")
        self.g2 = Garden.objects.create(name="过期园", altitudeBand="800m")
        self.g3 = Garden.objects.create(name="无票园", altitudeBand="900m")
        self.user = User.objects.create_user("witherer", password="123456")
        today = timezone.localdate()
        AirDuctCalibration.objects.create(
            garden=self.g1,
            calibrationDate=today,
            windSpeed=Decimal("3.2"),
            passed=True,
            recordedBy=self.user,
        )
        AirDuctCalibration.objects.create(
            garden=self.g2,
            calibrationDate=today - datetime.timedelta(days=10),
            windSpeed=Decimal("3.2"),
            passed=True,
            recordedBy=self.user,
        )

    def test_home_count_matches_filtered_list_rows(self):
        self.client.force_login(self.user)
        home = self.client.get(reverse("home"))
        self.assertEqual(home.context["valid_garden_count"], 1)

        filtered = self.client.get(reverse("garden_list"), {"valid": "1"})
        rows = list(filtered.context["gardens"])
        self.assertEqual(len(rows), home.context["valid_garden_count"])
        self.assertEqual([g.pk for g in rows], [self.g1.pk])

        full = self.client.get(reverse("garden_list"))
        self.assertEqual(len(list(full.context["gardens"])), 3)

    def test_nav_contains_calibration_link(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("home"))
        self.assertContains(resp, reverse("calibration_list"))
        self.assertContains(resp, "风道标定")
        self.assertContains(resp, "有效标定园数")


class SeedDataTests(TestCase):
    def test_one_seed_garden_has_no_valid_calibration(self):
        from apps.gardens.seed import ensure_seed_data

        ensure_seed_data()
        gardens = list(Garden.objects.all())
        valid = [g for g in gardens if has_valid_calibration(g)]
        invalid = [g for g in gardens if not has_valid_calibration(g)]
        self.assertEqual(len(gardens), 2)
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(invalid), 1)
