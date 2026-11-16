"""
Tests for scoring, band boundaries, the crisis flow, anonymous mode and privacy.
Run with:  python manage.py test
All answer profiles are made up - no real person's answers are used.
"""

from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile

from .forms import GuidanceForm
from .models import Assessment, Guidance, ScreeningTool
from .scoring import ScoringError, score_answers


def answers(values):
    """[1, 0, 2] -> {1: 1, 2: 0, 3: 2}"""
    return {i + 1: v for i, v in enumerate(values)}


def post_data(values, save=None):
    data = {f"q{i + 1}": str(v) for i, v in enumerate(values)}
    if save:
        data["save_result"] = "on"
    return data


class SeededTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Load the real tools, bands, guidance, resources and demo users.
        call_command("seed_mindcheck", stdout=StringIO())
        cls.phq9 = ScreeningTool.objects.get(slug="phq-9")
        cls.gad7 = ScreeningTool.objects.get(slug="gad-7")
        cls.who5 = ScreeningTool.objects.get(slug="who-5")


class ScoringTests(SeededTestCase):
    """Program totals and bands must match hand calculations at every band boundary."""

    def test_phq9_band_boundaries(self):
        # (answers, expected total, expected band label) - worked out by hand
        cases = [
            ([0, 0, 0, 0, 0, 0, 0, 0, 0], 0, "Minimal"),
            ([1, 1, 1, 1, 0, 0, 0, 0, 0], 4, "Minimal"),
            ([1, 1, 1, 1, 1, 0, 0, 0, 0], 5, "Mild"),
            ([1, 1, 1, 1, 1, 1, 1, 1, 1], 9, "Mild"),
            ([2, 2, 2, 2, 2, 0, 0, 0, 0], 10, "Moderate"),
            ([2, 2, 2, 2, 2, 2, 2, 0, 0], 14, "Moderate"),
            ([3, 3, 3, 3, 3, 0, 0, 0, 0], 15, "Moderately severe"),
            ([3, 3, 3, 3, 3, 2, 2, 0, 0], 19, "Moderately severe"),
            ([3, 3, 3, 3, 3, 3, 2, 0, 0], 20, "Severe"),
            ([3, 3, 3, 3, 3, 3, 3, 3, 3], 27, "Severe"),
        ]
        for values, total, label in cases:
            with self.subTest(total=total):
                result = score_answers(self.phq9, answers(values))
                self.assertEqual(result.raw_score, total)
                self.assertEqual(result.final_score, total)
                self.assertEqual(result.band.label, label)

    def test_gad7_band_boundaries(self):
        cases = [(0, "Minimal"), (4, "Minimal"), (5, "Mild"), (9, "Mild"),
                 (10, "Moderate"), (14, "Moderate"), (15, "Severe"), (21, "Severe")]
        for total, label in cases:
            values = [3] * (total // 3) + ([total % 3] if total % 3 else [])
            values += [0] * (7 - len(values))
            with self.subTest(total=total):
                result = score_answers(self.gad7, answers(values))
                self.assertEqual(result.final_score, total)
                self.assertEqual(result.band.label, label)

    def test_who5_is_multiplied_by_4_before_banding(self):
        # Raw 7 -> 28 (very low), raw 8 -> 32 (low), raw 12 -> 48 (low), raw 13 -> 52 (good)
        cases = [([0, 0, 0, 0, 0], 0, "Very low wellbeing"),
                 ([2, 2, 1, 1, 1], 28, "Very low wellbeing"),
                 ([2, 2, 2, 1, 1], 32, "Low wellbeing"),
                 ([3, 3, 2, 2, 2], 48, "Low wellbeing"),
                 ([3, 3, 3, 2, 2], 52, "Good wellbeing"),
                 ([5, 5, 5, 5, 5], 100, "Good wellbeing")]
        for values, final, label in cases:
            with self.subTest(final=final):
                result = score_answers(self.who5, answers(values))
                self.assertEqual(result.raw_score, sum(values))
                self.assertEqual(result.final_score, final)
                self.assertEqual(result.band.label, label)

    def test_high_bands_map_to_high_guidance(self):
        self.assertEqual(score_answers(self.phq9, answers([3] * 5 + [0] * 4)).band.guidance.tier, "high")
        self.assertEqual(score_answers(self.gad7, answers([3] * 5 + [0] * 2)).band.guidance.tier, "high")
        self.assertEqual(score_answers(self.who5, answers([1] * 5)).band.guidance.tier, "high")

    def test_safety_flag_only_from_item_9(self):
        self.assertTrue(score_answers(self.phq9, answers([0] * 8 + [1])).safety_flag)
        self.assertFalse(score_answers(self.phq9, answers([3] * 8 + [0])).safety_flag)
        self.assertFalse(score_answers(self.gad7, answers([3] * 7)).safety_flag)

    def test_missing_answer_is_rejected(self):
        with self.assertRaises(ScoringError):
            score_answers(self.phq9, answers([1] * 8))

    def test_out_of_range_answer_is_rejected(self):
        with self.assertRaises(ScoringError):
            score_answers(self.phq9, answers([1] * 8 + [7]))
        with self.assertRaises(ScoringError):
            score_answers(self.phq9, answers([1] * 8 + ["abc"]))

    def test_every_score_has_exactly_one_band(self):
        for tool in (self.phq9, self.gad7, self.who5):
            step = tool.score_multiplier
            for score in range(0, tool.max_final_score + 1, step):
                with self.subTest(tool=tool.short_name, score=score):
                    matches = tool.bands.filter(min_score__lte=score, max_score__gte=score).count()
                    self.assertEqual(matches, 1)


class AnonymousFlowTests(SeededTestCase):
    def setUp(self):
        session = self.client.session
        session["consent_given"] = True
        session.save()

    def test_consent_required_before_first_questionnaire(self):
        self.client.session.flush()
        fresh = self.client_class()
        response = fresh.get(reverse("screening:take", args=["phq-9"]))
        self.assertRedirects(response, reverse("screening:consent") + "?next=/screening/take/phq-9/")

    def test_consent_form_needs_tick(self):
        fresh = self.client_class()
        response = fresh.post(reverse("screening:consent"), {"next": "/screening/"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please tick the box")

    def test_anonymous_result_saves_nothing_to_database(self):
        before = Assessment.objects.count()
        response = self.client.post(reverse("screening:take", args=["gad-7"]), post_data([2] * 7))
        self.assertRedirects(response, reverse("screening:session_result"))
        self.assertEqual(Assessment.objects.count(), before)  # no new row written
        page = self.client.get(reverse("screening:session_result"))
        self.assertContains(page, "Your answers suggest moderate anxiety symptoms.")
        self.assertContains(page, "not saved")

    def test_clear_private_result(self):
        self.client.post(reverse("screening:take", args=["gad-7"]), post_data([0] * 7))
        self.client.post(reverse("screening:clear_session_result"))
        response = self.client.get(reverse("screening:session_result"))
        self.assertRedirects(response, reverse("screening:tools"))

    def test_item_9_shows_crisis_screen_first(self):
        response = self.client.post(reverse("screening:take", args=["phq-9"]), post_data([0] * 8 + [2]))
        self.assertRedirects(response, reverse("screening:crisis"))
        crisis = self.client.get(reverse("screening:crisis"))
        self.assertContains(crisis, "14416")
        self.assertContains(crisis, "112")
        self.assertContains(crisis, "Continue to my result")
        # After the crisis screen the user can continue (never blocked)
        result = self.client.get(reverse("screening:session_result"))
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, "Please speak to a professional soon")

    def test_result_cannot_skip_crisis_screen(self):
        self.client.post(reverse("screening:take", args=["phq-9"]), post_data([0] * 8 + [1]))
        # Going straight to the result URL still sends the user to the crisis screen first.
        response = self.client.get(reverse("screening:session_result"))
        self.assertRedirects(response, reverse("screening:crisis"))

    def test_no_crisis_screen_when_item_9_is_zero(self):
        response = self.client.post(reverse("screening:take", args=["phq-9"]), post_data([3] * 8 + [0]))
        self.assertRedirects(response, reverse("screening:session_result"))

    def test_missing_answers_show_errors_not_crash(self):
        response = self.client.post(reverse("screening:take", args=["phq-9"]), post_data([1] * 5))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please answer question 6.")

    def test_tampered_answer_value_is_rejected(self):
        before = Assessment.objects.count()
        response = self.client.post(reverse("screening:take", args=["phq-9"]), post_data([1] * 8 + [9]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertEqual(Assessment.objects.count(), before)

    def test_unknown_tool_gives_404(self):
        response = self.client.get(reverse("screening:take", args=["xyz-1"]))
        self.assertEqual(response.status_code, 404)

    def test_result_wording_is_never_diagnostic(self):
        for slug, values in (("phq-9", [3] * 8 + [0]), ("gad-7", [3] * 7), ("who-5", [0] * 5)):
            self.client.post(reverse("screening:take", args=[slug]), post_data(values))
            page = self.client.get(reverse("screening:session_result")).content.decode().lower()
            with self.subTest(slug=slug):
                self.assertIn("your answers suggest", page)
                self.assertNotIn("you have depression", page)
                self.assertIn("not a diagnosis", page)


class SignedInFlowTests(SeededTestCase):
    def setUp(self):
        self.user = User.objects.create_user("tester", "t@example.com", "Str0ng-pass!")
        Profile.objects.filter(user=self.user).update(consent_given_at="2026-11-01T10:00:00Z")
        self.other = User.objects.create_user("other", "o@example.com", "Str0ng-pass!")
        self.client.login(username="tester", password="Str0ng-pass!")

    def test_signed_in_result_is_saved_with_scores_only(self):
        response = self.client.post(reverse("screening:take", args=["phq-9"]), post_data([1] * 8 + [0], save=True))
        a = Assessment.objects.get(user=self.user)
        self.assertRedirects(response, a.get_absolute_url())
        self.assertEqual((a.raw_score, a.final_score, a.band.label), (8, 8, "Mild"))
        field_names = {f.name for f in Assessment._meta.get_fields()}
        self.assertNotIn("answers", field_names)  # individual answers are never stored

    def test_signed_in_user_can_choose_not_to_save(self):
        self.client.post(reverse("screening:take", args=["gad-7"]), post_data([1] * 7))
        self.assertEqual(Assessment.objects.filter(user=self.user).count(), 0)

    def test_cannot_view_someone_elses_result(self):
        result = score_answers(self.phq9, answers([0] * 9))
        theirs = Assessment.objects.create(user=self.other, tool=self.phq9, band=result.band,
                                           raw_score=0, final_score=0)
        response = self.client.get(theirs.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_history_filter_and_chart(self):
        for values in ([0] * 9, [2] * 8 + [0]):
            self.client.post(reverse("screening:take", args=["phq-9"]), post_data(values, save=True))
        response = self.client.get(reverse("screening:history"), {"tier": "high"})
        self.assertEqual(len(response.context["assessments"]), 1)  # 16 = moderately severe -> High
        self.assertEqual(response.context["charts"][0]["scores"], [0, 16])
        bad = self.client.get(reverse("screening:history"), {"tier": "nonsense"})
        self.assertContains(bad, "Unknown level filter")

    def test_delete_single_result(self):
        self.client.post(reverse("screening:take", args=["gad-7"]), post_data([0] * 7, save=True))
        a = Assessment.objects.get(user=self.user)
        self.client.post(reverse("screening:delete_assessment", args=[a.pk]))
        self.assertFalse(Assessment.objects.filter(pk=a.pk).exists())

    def test_member_cannot_open_counsellor_area(self):
        response = self.client.get(reverse("screening:counsellor"))
        self.assertEqual(response.status_code, 403)

    def test_history_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("screening:history"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])


class CounsellorTests(SeededTestCase):
    def setUp(self):
        self.client.login(username="counsellor1", password="MindCheck@2026")

    def test_dashboard_shows_totals(self):
        response = self.client.get(reverse("screening:counsellor"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "demo_member")  # no identities shown
        self.assertEqual(response.context["stats"]["assessments"], Assessment.objects.count())

    def test_update_guidance(self):
        url = reverse("screening:edit_guidance", args=["low"])
        response = self.client.post(url, {
            "headline": "Few symptoms at the moment", "advice": "Sleep well\nMove daily",
            "follow_up": "Check in again next month.", "retake_after_days": 30,
        })
        self.assertRedirects(response, reverse("screening:counsellor"))
        self.assertEqual(Guidance.objects.get(tier="low").headline, "Few symptoms at the moment")

    def test_guidance_rejects_diagnostic_or_medication_text(self):
        form = GuidanceForm(data={"headline": "You have depression", "advice": "x",
                                  "follow_up": "y", "retake_after_days": 10},
                            instance=Guidance.objects.get(tier="high"))
        self.assertFalse(form.is_valid())
        form = GuidanceForm(data={"headline": "ok", "advice": "Take medication daily",
                                  "follow_up": "y", "retake_after_days": 10},
                            instance=Guidance.objects.get(tier="high"))
        self.assertFalse(form.is_valid())

    def test_unknown_guidance_tier_404(self):
        self.assertEqual(self.client.get(reverse("screening:edit_guidance", args=["extreme"])).status_code, 404)
