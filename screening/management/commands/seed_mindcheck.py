"""
Loads the screening tools, guidance, resources and demo accounts.

    python manage.py seed_mindcheck

It is safe to run more than once: existing rows are updated, not duplicated.
Question wording follows the official PHQ-9, GAD-7 and WHO-5 forms.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Profile
from resources.models import Resource, ResourceCategory
from screening.models import AnswerChoice, Assessment, Guidance, Question, ScoreBand, ScreeningTool

DEMO_PASSWORD = "MindCheck@2026"
ADMIN_PASSWORD = "Admin@2026"

GUIDANCE = [
    {
        "tier": "low", "severity_rank": 1,
        "headline": "Few symptoms right now",
        "advice": "Keep a regular sleep and wake time.\nStay physically active most days.\nKeep in touch with friends and family.",
        "follow_up": "Retake this check in about a month, or sooner if things change.",
        "retake_after_days": 30, "show_professional_banner": False,
    },
    {
        "tier": "mild", "severity_rank": 2,
        "headline": "Some symptoms are present",
        "advice": "Set a steady sleep routine and limit screens before bed.\nAdd some daily movement, even a 20-minute walk.\nTalk to someone you trust about how you are feeling.\nCut back on alcohol and late-night caffeine.",
        "follow_up": "Retake this check in two weeks. If the feelings last, consider speaking to a counsellor.",
        "retake_after_days": 14, "show_professional_banner": False,
    },
    {
        "tier": "moderate", "severity_rank": 3,
        "headline": "Symptoms are likely affecting daily life",
        "advice": "Book a conversation with a counsellor or doctor in the next few weeks.\nUse the support directory below to find one near you.\nKeep up sleep, movement and contact with people you trust.",
        "follow_up": "Speak to a counsellor or doctor in the next few weeks.",
        "retake_after_days": 14, "show_professional_banner": False,
    },
    {
        "tier": "high", "severity_rank": 4,
        "headline": "Symptoms are significant",
        "advice": "Please contact a mental health professional soon.\nTele-MANAS (14416) is free, confidential and open 24/7.\nYour campus counselling cell can also help.\nConsider saving or printing this result to take to your appointment.",
        "follow_up": "Contact a professional soon.",
        "retake_after_days": 14, "show_professional_banner": True,
    },
]

FREQ_CHOICES = [(0, "Not at all"), (1, "Several days"), (2, "More than half the days"), (3, "Nearly every day")]
WHO5_CHOICES = [
    (5, "All of the time"), (4, "Most of the time"), (3, "More than half of the time"),
    (2, "Less than half of the time"), (1, "Some of the time"), (0, "At no time"),
]

TOOLS = [
    {
        "name": "Patient Health Questionnaire-9", "short_name": "PHQ-9", "slug": "phq-9",
        "domain": "Depression symptoms", "display_order": 1, "minutes_to_complete": 3,
        "description": "Nine questions about mood, interest, sleep, energy and concentration over the last two weeks.",
        "instructions": "Over the last 2 weeks, how often have you been bothered by any of the following problems?",
        "score_multiplier": 1, "higher_is_better": False,
        "citation": "Kroenke K, Spitzer RL, Williams JBW (2001). The PHQ-9. J Gen Intern Med 16(9):606-613.",
        "choices": FREQ_CHOICES,
        "questions": [
            "Little interest or pleasure in doing things",
            "Feeling down, depressed, or hopeless",
            "Trouble falling or staying asleep, or sleeping too much",
            "Feeling tired or having little energy",
            "Poor appetite or overeating",
            "Feeling bad about yourself, or that you are a failure or have let yourself or your family down",
            "Trouble concentrating on things, such as reading the newspaper or watching television",
            "Moving or speaking so slowly that other people could have noticed, or the opposite: being so fidgety or restless that you have been moving around a lot more than usual",
            "Thoughts that you would be better off dead, or of hurting yourself in some way",
        ],
        "safety_items": [9],
        "bands": [
            (0, 4, "Minimal", "Your answers suggest minimal or no depression symptoms right now.", "low"),
            (5, 9, "Mild", "Your answers suggest mild depression symptoms.", "mild"),
            (10, 14, "Moderate", "Your answers suggest moderate depression symptoms.", "moderate"),
            (15, 19, "Moderately severe", "Your answers suggest moderately severe depression symptoms.", "high"),
            (20, 27, "Severe", "Your answers suggest severe depression symptoms.", "high"),
        ],
    },
    {
        "name": "Generalised Anxiety Disorder-7", "short_name": "GAD-7", "slug": "gad-7",
        "domain": "Anxiety symptoms", "display_order": 2, "minutes_to_complete": 2,
        "description": "Seven questions about worry, nervousness and restlessness over the last two weeks.",
        "instructions": "Over the last 2 weeks, how often have you been bothered by the following problems?",
        "score_multiplier": 1, "higher_is_better": False,
        "citation": "Spitzer RL, Kroenke K, Williams JBW, Löwe B (2006). A brief measure for assessing generalized anxiety disorder: the GAD-7. Arch Intern Med 166(10):1092-1097.",
        "choices": FREQ_CHOICES,
        "questions": [
            "Feeling nervous, anxious, or on edge",
            "Not being able to stop or control worrying",
            "Worrying too much about different things",
            "Trouble relaxing",
            "Being so restless that it is hard to sit still",
            "Becoming easily annoyed or irritable",
            "Feeling afraid, as if something awful might happen",
        ],
        "safety_items": [],
        "bands": [
            (0, 4, "Minimal", "Your answers suggest minimal anxiety symptoms right now.", "low"),
            (5, 9, "Mild", "Your answers suggest mild anxiety symptoms.", "mild"),
            (10, 14, "Moderate", "Your answers suggest moderate anxiety symptoms.", "moderate"),
            (15, 21, "Severe", "Your answers suggest severe anxiety symptoms.", "high"),
        ],
    },
    {
        "name": "WHO-5 Well-Being Index", "short_name": "WHO-5", "slug": "who-5",
        "domain": "General wellbeing", "display_order": 3, "minutes_to_complete": 1,
        "description": "Five positive statements about how you have been feeling. Higher scores mean better wellbeing.",
        "instructions": "For each statement, choose the answer closest to how you have been feeling over the last two weeks.",
        "score_multiplier": 4, "higher_is_better": True,
        "citation": "WHO Regional Office for Europe (1998). Wellbeing Measures in Primary Health Care: the DepCare Project. Copenhagen.",
        "choices": WHO5_CHOICES,
        "questions": [
            "I have felt cheerful and in good spirits",
            "I have felt calm and relaxed",
            "I have felt active and vigorous",
            "I woke up feeling fresh and rested",
            "My daily life has been filled with things that interest me",
        ],
        "safety_items": [],
        # Bands are on the 0-100 scale (raw total x 4).
        "bands": [
            (0, 28, "Very low wellbeing", "Your answers suggest very low wellbeing. This can be a sign of depression and is worth talking to a professional about.", "high"),
            (29, 49, "Low wellbeing", "Your answers suggest low wellbeing that is worth following up.", "moderate"),
            (50, 100, "Good wellbeing", "Your answers suggest good wellbeing right now.", "low"),
        ],
    },
]

CATEGORIES = [
    ("National helpline", "national-helpline", "Free government helplines available across India."),
    ("Emergency", "emergency", "For immediate danger to life."),
    ("Campus counselling", "campus-counselling", "Counselling services inside the university."),
    ("Hospital", "hospital", "Psychiatry and mental health departments of hospitals."),
]

RESOURCES = [
    {
        "name": "Tele-MANAS National Mental Health Helpline", "category": "national-helpline",
        "description": "Free, confidential tele-counselling run by the Ministry of Health and Family Welfare. Callers can choose from about 20 languages and are referred on for further care when needed.",
        "phone": "14416", "alt_phone": "1-800-891-4416", "city": "All India", "hours": "24/7",
        "website": "https://telemanas.mohfw.gov.in/", "is_crisis_line": True,
    },
    {
        "name": "Emergency Response Support System", "category": "emergency",
        "description": "Single national emergency number for police, fire and ambulance when someone is in immediate danger.",
        "phone": "112", "alt_phone": "", "city": "All India", "hours": "24/7", "website": "", "is_crisis_line": True,
    },
    {
        "name": "University Counselling Cell", "category": "campus-counselling",
        "description": "Free and confidential sessions with trained counsellors for students and staff. Update the room and hours to match your campus before the demo.",
        "phone": "0000-000000", "alt_phone": "", "location": "Student Welfare Block (update)",
        "city": "Phagwara", "hours": "Mon-Sat, 9:00-17:00", "website": "", "is_crisis_line": False,
    },
    {
        "name": "Civil Hospital - Psychiatry OPD", "category": "hospital",
        "description": "Outpatient psychiatry department of the district government hospital. Low-cost consultations with a psychiatrist. Update the name and number for your district.",
        "phone": "0000-000000", "alt_phone": "", "location": "District Civil Hospital (update)",
        "city": "Jalandhar", "hours": "Mon-Sat, 9:00-14:00", "website": "", "is_crisis_line": False,
    },
    {
        "name": "National Ambulance Service", "category": "emergency",
        "description": "Free emergency ambulance service available in most states.",
        "phone": "108", "alt_phone": "", "city": "All India", "hours": "24/7", "website": "", "is_crisis_line": False,
    },
]

# Made-up history for the demo member: (days ago, tool slug, answers)
DEMO_HISTORY = [
    (42, "phq-9", [2, 2, 2, 1, 1, 2, 1, 1, 0]),
    (42, "gad-7", [2, 2, 2, 1, 1, 1, 1]),
    (28, "phq-9", [1, 2, 1, 1, 1, 1, 1, 1, 0]),
    (28, "who-5", [2, 2, 1, 2, 2]),
    (14, "phq-9", [1, 1, 1, 1, 0, 1, 1, 0, 0]),
    (14, "gad-7", [1, 1, 1, 1, 0, 1, 1]),
    (3, "phq-9", [1, 0, 1, 1, 0, 0, 1, 0, 0]),
    (3, "who-5", [3, 3, 3, 2, 3]),
]


class Command(BaseCommand):
    help = "Load screening tools, guidance, resources and demo users for MindCheck."

    @transaction.atomic
    def handle(self, *args, **options):
        guidance = {}
        for g in GUIDANCE:
            obj, _ = Guidance.objects.update_or_create(tier=g["tier"], defaults=g)
            guidance[g["tier"]] = obj
        self.stdout.write(f"Guidance tiers: {len(guidance)}")

        for t in TOOLS:
            tool, _ = ScreeningTool.objects.update_or_create(
                slug=t["slug"],
                defaults={k: t[k] for k in (
                    "name", "short_name", "domain", "description", "instructions", "score_multiplier",
                    "higher_is_better", "citation", "display_order", "minutes_to_complete")},
            )
            for order, (value, label) in enumerate(t["choices"]):
                AnswerChoice.objects.update_or_create(
                    tool=tool, value=value, defaults={"label": label, "display_order": order})
            for number, text in enumerate(t["questions"], start=1):
                Question.objects.update_or_create(
                    tool=tool, number=number,
                    defaults={"text": text, "is_safety_item": number in t["safety_items"]})
            for lo, hi, label, interp, tier in t["bands"]:
                ScoreBand.objects.update_or_create(
                    tool=tool, min_score=lo,
                    defaults={"max_score": hi, "label": label, "interpretation": interp, "guidance": guidance[tier]})
            self.stdout.write(f"Tool {tool.short_name}: {tool.questions.count()} questions, {tool.bands.count()} bands")

        cats = {}
        for name, slug, desc in CATEGORIES:
            cats[slug], _ = ResourceCategory.objects.update_or_create(slug=slug, defaults={"name": name, "description": desc})
        for r in RESOURCES:
            data = dict(r)
            name, city = data.pop("name"), data.pop("city")
            data["category"] = cats[data["category"]]
            data["last_verified"] = date(2026, 11, 14)
            Resource.objects.update_or_create(name=name, city=city, defaults=data)
        self.stdout.write(f"Resources: {Resource.objects.count()}")

        admin, created = User.objects.get_or_create(
            username="admin", defaults={"email": "admin@mindcheck.local", "is_staff": True, "is_superuser": True})
        if created:
            admin.set_password(ADMIN_PASSWORD)
            admin.save()
        Profile.objects.filter(user=admin).update(role=Profile.Role.COUNSELLOR, consent_given_at=timezone.now())

        counsellor, created = User.objects.get_or_create(
            username="counsellor1", defaults={"first_name": "Asha", "last_name": "Verma", "email": "counsellor1@mindcheck.local"})
        if created:
            counsellor.set_password(DEMO_PASSWORD)
            counsellor.save()
        Profile.objects.filter(user=counsellor).update(role=Profile.Role.COUNSELLOR, consent_given_at=timezone.now())

        member, created = User.objects.get_or_create(
            username="demo_member", defaults={"first_name": "Demo", "last_name": "Member", "email": "member@mindcheck.local"})
        if created:
            member.set_password(DEMO_PASSWORD)
            member.save()
        Profile.objects.filter(user=member).update(role=Profile.Role.MEMBER, consent_given_at=timezone.now())

        # Rebuild the made-up history so the trend chart has data.
        from screening.scoring import score_answers
        member.assessments.all().delete()
        now = timezone.now()
        for days_ago, slug, answers in DEMO_HISTORY:
            tool = ScreeningTool.objects.get(slug=slug)
            res = score_answers(tool, {i + 1: v for i, v in enumerate(answers)})
            a = Assessment.objects.create(
                user=member, tool=tool, band=res.band, raw_score=res.raw_score,
                final_score=res.final_score, safety_flag=res.safety_flag)
            Assessment.objects.filter(pk=a.pk).update(created_at=now - timedelta(days=days_ago))
        self.stdout.write(f"Demo history: {member.assessments.count()} assessments")

        self.stdout.write(self.style.SUCCESS(
            f"Done. Logins - admin / {ADMIN_PASSWORD}, counsellor1 / {DEMO_PASSWORD}, demo_member / {DEMO_PASSWORD}"))
