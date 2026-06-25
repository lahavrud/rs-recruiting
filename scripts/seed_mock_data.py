#!/usr/bin/env python3
"""הרצת נתוני בדיקה לפיתוח מקומי.

שימוש:
    PYTHONPATH=. uv run python scripts/seed_mock_data.py
    PYTHONPATH=. uv run python scripts/seed_mock_data.py --reset  # מאפס לפני ההזרעה

    # סביבת staging — מוריד קו"ח אמיתיים מ-S3:
    PYTHONPATH=. uv run python scripts/seed_mock_data.py --reset \\
        --resumes-s3-prefix s3://bucket/seed-fixtures/resumes/

    # פיתוח מקומי עם קו"ח מספריית פייל-סיסטם:
    PYTHONPATH=. uv run python scripts/seed_mock_data.py --reset \\
        --resumes-dir scripts/fixtures/resumes-real/

הרץ לאחר הפעלת הבקאנד (docker compose up) והוספת משתמש מנהל.

יוצר:
    - 1 משתמש מנהל (admin@rsrecruit.com / Admin123!)
    - 20 חברות עם פרופילים (3 ענפים: מתקנים, אבטחה, ניקיון)
    - 15 משרות (סטטוסים מעורבים, מפוזרות בין החברות בכל ענף)
    - 50 פרופילי מועמדים (25 רשומים עם משתמש + הסכמת פרטיות, 25 לידים אנונימיים)
    - כ-100 מועמדויות (סטטוסים שונים, עם תשובות שאלון ראיון וקובץ קו"ח)
"""

import argparse
import asyncio
import hashlib
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select

from src.core.infrastructure.database import async_session, init_db
from src.core.infrastructure.security import get_password_hash
from src.core.services.storage import get_storage_provider
from src.enums import ApplicationStatus, JobStatus, UserRole
from src.models import (
    Application,
    AuditLog,
    CandidateProfile,
    CompanyProfile,
    InviteToken,
    Job,
    User,
)
from src.services.utils.audit import record_audit_event
from src.services.utils.legal import (
    CURRENT_PRIVACY_POLICY_VERSION,
    CURRENT_TERMS_OF_SERVICE_VERSION,
)

# Resume PDFs used as placeholder uploads in seed data — cycled round-robin
# across candidates. Override at runtime with --resumes-dir or --resumes-s3-prefix
# to use realistic synthetic resumes so the matching engine produces meaningful scores.
_RESUME_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "resumes"
_RESUME_FIXTURES = sorted(_RESUME_FIXTURES_DIR.glob("*.pdf"))


def _resolve_resume_fixtures(
    resumes_dir: str | None, resumes_s3_prefix: str | None
) -> list[Path]:
    """Return the list of PDF paths to cycle through for candidate resumes.

    Priority: --resumes-dir > --resumes-s3-prefix > built-in fixtures.
    S3 files are downloaded to a temp dir that persists for the process lifetime.
    """
    if resumes_dir:
        paths = sorted(Path(resumes_dir).glob("*.pdf"))
        if not paths:
            raise SystemExit(f"--resumes-dir {resumes_dir!r} contains no .pdf files")
        print(f'  📄 קו"ח מספריה: {resumes_dir} ({len(paths)} קבצים)\n')
        return paths

    if resumes_s3_prefix:
        import boto3

        prefix = resumes_s3_prefix.rstrip("/")
        if not prefix.startswith("s3://"):
            raise SystemExit(
                f"--resumes-s3-prefix must start with s3://, got {prefix!r}"
            )
        bucket, key_prefix = prefix[5:].split("/", 1)
        client = boto3.client("s3")
        paginator = client.get_paginator("list_objects_v2")
        tmp = Path(tempfile.mkdtemp())
        paths: list[Path] = []
        for page in paginator.paginate(Bucket=bucket, Prefix=key_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.lower().endswith(".pdf"):
                    dest = tmp / Path(key).name
                    client.download_file(bucket, key, str(dest))
                    paths.append(dest)
        if paths:
            print(f'  📄 קו"ח מ-S3 ({prefix}): {len(paths)} קבצים\n')
            return sorted(paths)
        print('  ⚠️  לא נמצאו קו"ח ב-S3, משתמש בקבצי ברירת מחדל\n')

    return _RESUME_FIXTURES


# Reserved documentation IP (RFC 5737 TEST-NET-3) — never a real client address
_MOCK_CONSENT_IP = "203.0.113.10"
_MOCK_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# ── מנהל ──
ADMIN_EMAIL = "admin@rsrecruit.com"
ADMIN_PASSWORD = "Admin123!"  # pragma: allowlist secret

# ── מועמד רשום ──
CANDIDATE_PASSWORD = "Candidate123!"  # pragma: allowlist secret

# Name pools used to generate companies' contact names and candidates'
# full names deterministically (cycled via modulo, no `random`).
FIRST_NAMES = [
    "אחמד",
    "מאיה",
    "יוסי",
    "רינת",
    "שלמה",
    "ליאת",
    "עמיר",
    "סאמי",
    "דנה",
    "אלון",
    "מירב",
    "תומר",
    "אורית",
    "גיא",
    "שירה",
    "רועי",
    "נועה",
    "איתי",
    "טל",
    "הדס",
    "יואב",
    "כרמית",
    "עידו",
    "ענת",
    "בועז",
    "מיכל",
    "אסף",
    "רוני",
    "אביב",
    "נטע",
]
LAST_NAMES = [
    "פאהום",
    "בן-דוד",
    "ממן",
    "שפירא",
    "אברהם",
    "אוחנה",
    "גולן",
    "ג'בארין",
    "לוי",
    "כהן",
    "מזרחי",
    "פרץ",
    "ביטון",
    "אזולאי",
    "דהן",
    "חדד",
    "אלקיים",
    "סבן",
    "נחום",
    "אשכנזי",
    "וקנין",
    "טל",
    "ברק",
    "שמש",
]

# ── חברות ──
# 20 companies grouped by sector — sectors map 1:1 to the JOBS_BY_SECTOR
# groups below. Each sector has more companies than postings, so a few
# companies in every sector have no jobs yet (realistic "registered but
# hasn't posted" state).
_FACILITIES_COMPANY_NAMES = [
    'פתרונות מתקנים בע"מ',
    'נדל"ן טכני בע"מ',
    "תחזוקת מבנים מאוחדת",
    'אחזקה כוללת בע"מ',
    "סיסטם פתרונות מתקנים",
    'מבני איכות בע"מ',
    "תפעול ואחזקה ישראל",
]
_SECURITY_COMPANY_NAMES = [
    "שריון — אבטחה ותחזוקה",
    "מגן אבטחה ובקרה",
    "פאר אבטחה",
    'ביטחון כוללני בע"מ',
    "נץ פתרונות אבטחה",
    "סייבר-גארד אבטחה פיזית",
    'שומרי הסף בע"מ',
]
_CLEANING_COMPANY_NAMES = [
    "קלינפרו שירותי מתקנים",
    'נקיון פלוס בע"מ',
    "ספארקל שירותי ניקיון",
    'כללי-נקי בע"מ',
    "גרין קלין שירותים",
    "אקופלוס ניקיון ומיחזור",
]
_COMPANY_NAMES = [
    *_FACILITIES_COMPANY_NAMES,
    *_SECURITY_COMPANY_NAMES,
    *_CLEANING_COMPANY_NAMES,
]
_COMPANY_ADDRESSES = [
    "רח׳ הברזל 32, תל אביב",
    "שדרות רוטשילד 15, תל אביב",
    "רח׳ המסגר 22, תל אביב",
    "רח׳ העצמאות 10, נתניה",
    "שדרות בן גוריון 5, חיפה",
    "רח׳ הנשיא 8, ירושלים",
    "רח׳ העמל 3, ראשון לציון",
    "רח׳ ויצמן 12, פתח תקווה",
    "רח׳ הסיבים 7, אשדוד",
    "רח׳ סוקולוב 20, הרצליה",
    "רח׳ ביאליק 4, רמת גן",
    "רח׳ ההסתדרות 9, חולון",
    "רח׳ אחוזה 50, רעננה",
    "רח׳ עזריאלי 1, מודיעין",
    "רח׳ ויצמן 30, כפר סבא",
    "רח׳ הרצל 18, רחובות",
    "רח׳ הנגיד 6, אשקלון",
    "רח׳ הגעתון 2, נהריה",
    "שדרות התמרים 14, אילת",
    "רח׳ הירדן 11, טבריה",
]


def _build_companies() -> list[dict]:
    companies = []
    for i, name in enumerate(_COMPANY_NAMES):
        n = i + 1
        companies.append(
            {
                "email": f"company{n}@example.com",
                "password": "Company123!",  # pragma: allowlist secret
                "company_name": name,
                "company_id": f"5112345{n:02d}",  # ח.פ — 9 digits
                "address": _COMPANY_ADDRESSES[i % len(_COMPANY_ADDRESSES)],
                "contact_first_name": FIRST_NAMES[(i * 3 + 5) % len(FIRST_NAMES)],
                "contact_last_name": LAST_NAMES[(i * 5 + 3) % len(LAST_NAMES)],
                "contact_mobile_phone": f"05000002{n:02d}",
            }
        )
    return companies


COMPANIES = _build_companies()


def _reqs(*items: str) -> list[dict]:
    return [{"text": t} for t in items]


# ── משרות ──
# 15 postings total, grouped by sector. Each sector's jobs are handed out
# one-per-company to the first `len(jobs)` companies in that sector — see
# `_SECTOR_COMPANY_OFFSETS` below.
JOBS_BY_SECTOR = [
    # מתקנים
    [
        {
            "title": "מנהל מתקנים בכיר",
            "short_description": "אחריות מלאה על קמפוס מסחרי פעיל בלב תל אביב.",
            "description": "ניהול קמפוס מסחרי — מיזוג, חשמל, אינסטלציה וניקיון.",
            "requirements": _reqs(
                "5+ שנות ניסיון בניהול מתקנים",
                "תואר הנדסה",
                "ניסיון בניהול צוותים רב-תחומיים",
            ),
            "tags": ["רכב צמוד", "ניהול בכיר", "קמפוס מסחרי"],
            "is_featured": True,
            "location": "תל אביב",
            "salary_min": 18000,
            "salary_max": 25000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "טכנאי מיזוג אוויר",
            "short_description": "תפקיד שטח עם רכב חברה ולקוחות מגוונים באזור המרכז.",
            "description": "התקנה ותחזוקת מערכות מיזוג אצל לקוחות מגוונים.",
            "requirements": _reqs(
                "3+ שנות ניסיון",
                "תעודת מיזוג",
                "רישיון נהיגה בתוקף",
            ),
            "tags": ["רכב צמוד", "תפקיד שטח"],
            "is_featured": False,
            "location": "תל אביב",
            "salary_min": 12000,
            "salary_max": 17000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "מהנדס מערכות בניין",
            "short_description": "תפקיד הנדסי במרכזים מסחריים בהרצליה פיתוח.",
            "description": "ניהול מערכות BMS ואופטימיזציית צריכת אנרגיה.",
            "requirements": _reqs(
                "תואר הנדסה מכנית או חשמלית",
                "3+ שנות ניסיון ב-BMS",
                "ידע בקרי מערכת מתקדמים",
            ),
            "tags": ["BMS", "הנדסה", "אנרגיה"],
            "is_featured": False,
            "location": "הרצליה",
            "salary_min": 15000,
            "salary_max": 22000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "מנהל תחזוקה חשמלית",
            "short_description": "ניהול צוות חשמלאים על-פני 5 נכסי לקוח באזור גוש דן.",
            "description": "פיקוח על צוות חשמלאים ב-5 נכסי לקוח.",
            "requirements": _reqs(
                "הנדסאי חשמל",
                "5+ שנות ניסיון",
                "רישיון משרד האנרגיה",
            ),
            "tags": ["ניהול צוות"],
            "is_featured": False,
            "location": "תל אביב",
            "salary_min": 14000,
            "salary_max": 20000,
            "status": JobStatus.PENDING_APPROVAL,
        },
        {
            "title": "ראש צוות אינסטלציה",
            "short_description": "ניהול תחזוקת אינסטלציה בקמפוס בית חולים פעיל.",
            "description": "ניהול תחזוקת אינסטלציה בקמפוס בית חולים.",
            "requirements": _reqs(
                "10+ שנות ניסיון",
                "3+ שנות ניהול",
                "תעודת מים",
            ),
            "tags": ["בית חולים", "ניהול"],
            "is_featured": False,
            "location": "רמת גן",
            "salary_min": 16000,
            "salary_max": 22000,
            "status": JobStatus.CLOSED,
        },
    ],
    # שריון — אבטחה ותחזוקה
    [
        {
            "title": "מנהל מבצעי ביטחון",
            "short_description": "ניהול אבטחת 8 מבנים מסחריים וצוות של 40 מאבטחים.",
            "description": "ניהול אבטחת 8 מבנים מסחריים ו-40 מאבטחים.",
            "requirements": _reqs(
                "5+ שנות ניסיון בתחום הביטחון",
                "רישיון מנהל ביטחון ממשרד הפנים",
                "כושר ניהולי גבוה",
            ),
            "tags": ["רכב צמוד", "ניהול בכיר", "כוננות"],
            "is_featured": True,
            "location": "תל אביב",
            "salary_min": 18000,
            "salary_max": 24000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "רכז בטיחות אש",
            "short_description": "הטמעת תוכניות בטיחות אש במספר אתרי לקוחות בצפון.",
            "description": "הטמעת תוכניות בטיחות אש ופיקוח על ציוד כיבוי.",
            "requirements": _reqs(
                "תעודת בטיחות אש בתוקף",
                "3+ שנות ניסיון",
                "הדרכת עזרה ראשונה",
            ),
            "tags": ["בטיחות", "תפקיד שטח"],
            "is_featured": False,
            "location": "חיפה",
            "salary_min": 12000,
            "salary_max": 16000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "טכנאי בקרת כניסה",
            "short_description": "התקנת מערכות בקרת כניסה ובקרת גישה אצל לקוחות.",
            "description": "התקנת מערכות RFID, ביומטריה ואינטרקום.",
            "requirements": _reqs(
                "2+ שנות ניסיון בבקרת כניסה",
                "רקע באלקטרוניקה",
                "ידע במערכות RFID",
            ),
            "tags": ["טכנאות", "RFID"],
            "is_featured": False,
            "location": "פתח תקווה",
            "salary_min": 10000,
            "salary_max": 14000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "מאבטח — קמפוס היי-טק",
            "short_description": "תפקיד אבטחה בקמפוס טכנולוגי באזור הרצליה פיתוח.",
            "description": "סיורים, ניטור CCTV וקבלת אורחים בקמפוס טכנולוגי.",
            "requirements": _reqs(
                "רישיון מאבטח בתוקף",
                "עברית ואנגלית בסיסית",
                "כושר גופני סביר",
            ),
            "tags": ["משמרות"],
            "is_featured": False,
            "location": "הרצליה",
            "salary_min": 8000,
            "salary_max": 11000,
            "status": JobStatus.PENDING_APPROVAL,
        },
        {
            "title": "מנהל מערכות CCTV",
            "short_description": "ניהול תשתית CCTV ארגונית הכוללת 200+ מצלמות.",
            "description": "ניהול Milestone XProtect, בריאות מצלמות ואחסון.",
            "requirements": _reqs(
                "הסמכת Milestone XProtect",
                "3+ שנות ניסיון",
                "זמינות לכוננות",
            ),
            "tags": ["CCTV", "Milestone", "כוננות"],
            "is_featured": False,
            "location": "תל אביב",
            "salary_min": 14000,
            "salary_max": 19000,
            "status": JobStatus.CLOSED,
        },
    ],
    # קלינפרו שירותי מתקנים
    [
        {
            "title": "מנהל פעילות ניקיון",
            "short_description": "ניהול 12 נכסים פעילים וצוות של 80+ עובדים בירושלים.",
            "description": "ניהול ניקיון ב-12 נכסים וצוות של 80+ עובדים.",
            "requirements": _reqs(
                "5+ שנות ניסיון בניהול ניקיון",
                "שליטה בעברית ובערבית",
                "ניסיון ניהול צוותים גדולים",
            ),
            "tags": ["ניהול בכיר", "רכב צמוד"],
            "is_featured": True,
            "location": "ירושלים",
            "salary_min": 16000,
            "salary_max": 22000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "מומחה ניקיון תעשייתי",
            "short_description": "תפקיד מקצועי במפעלי מזון ומחסנים לוגיסטיים באשדוד.",
            "description": "ניקיון מפעלי מזון ומחסנים. תפעול ציוד תעשייתי.",
            "requirements": _reqs(
                "2+ שנות ניסיון בניקיון תעשייתי",
                "הסמכת חומרים מסוכנים",
                "כושר גופני",
            ),
            "tags": ["תעשייה", "חומרים מסוכנים"],
            "is_featured": False,
            "location": "אשדוד",
            "salary_min": 9000,
            "salary_max": 13000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "מנהל פסולת ומיחזור",
            "short_description": "פיקוח על מערך מיחזור ופינוי פסולת ללקוחות עסקיים.",
            "description": "פיקוח על מיחזור ופינוי פסולת עבור לקוחות עסקיים.",
            "requirements": _reqs(
                "3+ שנות ניסיון בתחום הפסולת",
                "ידע ברגולציית משרד הסביבה",
                "יכולת עבודה מול רשויות",
            ),
            "tags": ["סביבה", "רגולציה"],
            "is_featured": False,
            "location": "ראשון לציון",
            "salary_min": 11000,
            "salary_max": 16000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "מפקח איכות ניקיון",
            "short_description": "ביקורות איכות בלתי מוכרזות באתרי לקוחות בכל הארץ.",
            "description": "ביקורות איכות בלתי מוכרזות בכל אתרי הלקוחות.",
            "requirements": _reqs(
                "2+ שנות ניסיון",
                "עין חדה לפרטים",
                "רכב פרטי",
            ),
            "tags": ["רכב צמוד", "תפקיד שטח"],
            "is_featured": False,
            "location": "תל אביב",
            "salary_min": 10000,
            "salary_max": 14000,
            "status": JobStatus.PENDING_APPROVAL,
        },
        {
            "title": "ראש צוות ניקיון",
            "short_description": "ניהול צוות בקומפלקס משרדי ממשלתי באזור ירושלים.",
            "description": "ניהול 6 עובדים בקומפלקס משרדי ממשלתי.",
            "requirements": _reqs(
                "ניסיון ניהולי",
                "אוריינות מחשב",
                "אישור ביטחון",
            ),
            "tags": ["ממשלתי"],
            "is_featured": False,
            "location": "ירושלים",
            "salary_min": 9000,
            "salary_max": 13000,
            "status": JobStatus.CLOSED,
        },
    ],
]

# Index of the first company (within COMPANIES) for each sector — jobs in
# JOBS_BY_SECTOR[s] go one-per-company to COMPANIES[offset], COMPANIES[offset+1], ...
_SECTOR_COMPANY_OFFSETS = [
    0,
    len(_FACILITIES_COMPANY_NAMES),
    len(_FACILITIES_COMPANY_NAMES) + len(_SECURITY_COMPANY_NAMES),
]

# ── מועמדים ──
# `registered` candidates have a linked CANDIDATE user account (password
# CANDIDATE_PASSWORD) and privacy/ToS consent on file — mirroring a
# completed /register-candidate + activation flow. The rest are anonymous
# leads created via the public apply form (no user_id, no consent).
# `service_concept` / `salary_expectations` / `strength` / `growth_area` are
# interview-questionnaire answers — these live on `Application`, not
# `CandidateProfile` (see commit 6866251).
INTERVIEW_ANSWERS = [
    {
        "service_concept": (
            "שירות טוב הוא זמינות ועמידה בהתחייבויות. "
            "אני מאמין בתקשורת יזומה — לעדכן לפני שמבקשים."
        ),
        "salary_expectations": "18,000–22,000 ₪ לחודש",
        "strength": "רגוע תחת לחץ ומאוד שיטתי",
        "growth_area": "לפעמים מרבה לעסוק בפרטים הקטנים",
    },
    {
        "service_concept": (
            "הלקוח צריך להרגיש שיש מישהו שאחראי. "
            "אני מגדיר/ה ציפיות ברורות מהרגע הראשון ומעדכן/ת בכל שלב."
        ),
        "salary_expectations": "23,000–28,000 ₪ לחודש",
        "strength": "מנהיגות חזקה ותיאום צוות",
        "growth_area": "נוטה לקחת על עצמי יותר מדי משימות",
    },
    {
        "service_concept": (
            "שירות טוב זה לעשות את העבודה נכון בפעם הראשונה. "
            "אני לא עוזב אתר עד שהדבר תוקן לגמרי."
        ),
        "salary_expectations": "12,000–15,000 ₪ לחודש",
        "strength": "אמין, חרוץ, מצוין עם אנשים",
        "growth_area": "אנגלית מוגבלת",
    },
    {
        "service_concept": (
            "שירות טוב מבוסס על סדר ומעקב. "
            "כל פנייה מקבלת מענה, כל הבטחה מתועדת ומקוימת."
        ),
        "salary_expectations": "16,000–20,000 ₪ לחודש",
        "strength": "ארגון ותכנון מעולים",
        "growth_area": "לעיתים מתקשה להאציל משימות",
    },
    {
        "service_concept": (
            "מסביר/ה ללקוח מה נעשה ולמה — לא רק מתקן ועוזב. "
            "אנשים צריכים להבין את הבעיה כדי לסמוך על הפתרון."
        ),
        "salary_expectations": "14,000–18,000 ₪ לחודש",
        "strength": "פותר בעיות מעשי, לומד מהר",
        "growth_area": "מעדיף עבודה עצמאית על פני צוות גדול",
    },
    {
        "service_concept": (
            "כל פנייה — גם הקטנה ביותר — מקבלת יחס מכובד ומהיר. "
            "הרושם הראשוני הוא כל הביקור."
        ),
        "salary_expectations": "10,000–13,000 ₪ לחודש",
        "strength": "ידידותי/ת, מאורגן/ת, נוכחות טלפונית מצוינת",
        "growth_area": "אין רקע טכני",
    },
    {
        "service_concept": (
            "שירות אמיתי הוא מניעת בעיות לפני שהן צצות. "
            "אני מעדיף/ה תחזוקה מונעת על פני תיקון בשעת חירום."
        ),
        "salary_expectations": "25,000–32,000 ₪ לחודש",
        "strength": "חשיבה אסטרטגית וידע טכני רחב",
        "growth_area": "חסר/ת סבלנות לתהליכים איטיים",
    },
    {
        "service_concept": (
            "לקוח מרוצה מביא לקוח נוסף. אני עובד/ת כאילו כל עבודה היא כרטיס הביקור שלי."
        ),
        "salary_expectations": "11,000–14,000 ₪ לחודש",
        "strength": "עובד/ת קשה ואמין/ה ביותר",
        "growth_area": "השכלה פורמלית מוגבלת (כיתה י')",
    },
    {
        "service_concept": (
            "שירות טוב מתחיל בהקשבה — להבין מה הלקוח באמת צריך לפני שמציעים פתרון."
        ),
        "salary_expectations": "13,000–17,000 ₪ לחודש",
        "strength": "תקשורת בין-אישית מצוינת",
        "growth_area": "עדיין צובר/ת ניסיון בניהול פרויקטים גדולים",
    },
    {
        "service_concept": (
            "אני מאמין/ה בשקיפות מלאה — אם משהו לא ייגמר בזמן, הלקוח יודע על זה מראש."
        ),
        "salary_expectations": "15,000–19,000 ₪ לחודש",
        "strength": "אחריות גבוהה ועמידה בלוחות זמנים",
        "growth_area": "לומד/ת להעביר משימות במקום לעשות הכל בעצמי/ה",
    },
    {
        "service_concept": (
            "שירות מצוין הוא כזה שהלקוח לא צריך לחשוב עליו פעמיים — הכול פשוט קורה."
        ),
        "salary_expectations": "20,000–26,000 ₪ לחודש",
        "strength": "יוזמה ועבודה עצמאית",
        "growth_area": "מעדיף/ה תהליכים מסודרים על פני אד-הוק",
    },
    {
        "service_concept": (
            "אני רואה בכל אתר הזדמנות לבנות אמון ארוך-טווח עם הלקוח, לא רק לסגור משימה."
        ),
        "salary_expectations": "17,000–21,000 ₪ לחודש",
        "strength": "יחסי אנוש מעולים ויכולת הדרכה",
        "growth_area": "משתפר/ת בתעדוף בין כמה משימות דחופות במקביל",
    },
]


def _build_candidates() -> list[dict]:
    candidates = []
    for i in range(50):
        n = i + 1
        first = FIRST_NAMES[i % len(FIRST_NAMES)]
        last = LAST_NAMES[i % len(LAST_NAMES)]
        full_name = f"{first} {last}"
        linkedin_url = (
            None if i % 3 == 0 else f"https://www.linkedin.com/in/example-candidate-{n}"
        )
        answers = INTERVIEW_ANSWERS[i % len(INTERVIEW_ANSWERS)]
        candidates.append(
            {
                "full_name": full_name,
                "email": f"candidate{n}@example.com",
                "phone": f"0500000{n:03d}",
                "linkedin_url": linkedin_url,
                "registered": i % 2 == 0,
                **answers,
            }
        )
    return candidates


CANDIDATES = _build_candidates()


NOW = datetime.now(timezone.utc)


def _days_ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


# Admin notes per application outcome
ADMIN_NOTES_BY_OUTCOME = {
    "approved": "מועמד מתאים, עם ניסיון רלוונטי. מאושר לראיון.",
    "rejected_direct": "הניסיון אינו עומד בדרישות המינימום לתפקיד.",
    "rejected_after_review": (
        "המועמד עבר סינון ראשוני, אך לאחר שיחה עם הצוות לא נמצאה התאמה להמשך התהליך."
    ),
    "hired": "התאמה מעולה. המועמד קיבל את ההצעה ואישר תחילת עבודה.",
}


_StatusTransition = tuple[datetime, ApplicationStatus, ApplicationStatus]
_StatusHistory = tuple[list[_StatusTransition], datetime, str | None]

_NEW = ApplicationStatus.NEW
_APPROVED = ApplicationStatus.APPROVED_BY_ADMIN
_REJECTED = ApplicationStatus.REJECTED
_HIRED = ApplicationStatus.HIRED


def _status_history(
    app_status: ApplicationStatus, applied_at: datetime, *, via_review: bool
) -> _StatusHistory:
    """Build a realistic status-transition history for an application.

    Returns (transition events, last updated_at, admin note).
    """
    if app_status == _NEW:
        return [], applied_at, None

    if app_status == _APPROVED:
        approved_at = applied_at + timedelta(days=2)
        return (
            [(approved_at, _NEW, _APPROVED)],
            approved_at,
            ADMIN_NOTES_BY_OUTCOME["approved"],
        )

    if app_status == _REJECTED:
        if via_review:
            approved_at = applied_at + timedelta(days=2)
            rejected_at = applied_at + timedelta(days=6)
            return (
                [(approved_at, _NEW, _APPROVED), (rejected_at, _APPROVED, _REJECTED)],
                rejected_at,
                ADMIN_NOTES_BY_OUTCOME["rejected_after_review"],
            )
        rejected_at = applied_at + timedelta(days=1)
        return (
            [(rejected_at, _NEW, _REJECTED)],
            rejected_at,
            ADMIN_NOTES_BY_OUTCOME["rejected_direct"],
        )

    # HIRED — always passes through admin approval before being hired
    approved_at = applied_at + timedelta(days=2)
    hired_at = applied_at + timedelta(days=9)
    return (
        [(approved_at, _NEW, _APPROVED), (hired_at, _APPROVED, _HIRED)],
        hired_at,
        ADMIN_NOTES_BY_OUTCOME["hired"],
    )


def _print_result(entity: str, action: str, detail: str = "") -> None:
    icon = "✅" if action == "created" else "⏭️"
    print(f"  {icon} {entity}: {detail}")


async def reset(session_factory) -> None:
    """מוחק את כל נתוני הבדיקה הקיימים (מועמדים, מועמדויות, משרות, חברות, משתמשים)."""
    print("🧹 מוחק נתוני בדיקה קיימים...\n")
    async with session_factory() as session:
        # InviteToken.created_by_admin_id has no ON DELETE rule — clear it
        # first. Deleting User then cascades to its CompanyProfile -> Jobs ->
        # Applications. Deleting CandidateProfile cascades to any remaining
        # Applications for that candidate. AuditLog rows reference their
        # target by id with no FK, so they're cleared explicitly.
        await session.execute(delete(AuditLog))
        await session.execute(delete(InviteToken))
        await session.execute(delete(User))
        await session.execute(delete(CandidateProfile))
        await session.commit()
    print("  ✅ הנתונים הקיימים נמחקו\n")


async def seed(resume_fixtures: list[Path] | None = None) -> None:
    """פונקציית הזרעה הראשית."""
    if resume_fixtures is None:
        resume_fixtures = _RESUME_FIXTURES
    print("🌱 מזריע נתוני בדיקה עבור RS Recruiting\n")

    async with async_session() as session:
        # ── מנהל ──
        result = await session.execute(select(User).where(User.email == ADMIN_EMAIL))
        admin = result.scalar_one_or_none()
        if admin:
            admin_user = admin
            _print_result("מנהל", "skipped", ADMIN_EMAIL)
        else:
            admin_user = User(
                email=ADMIN_EMAIL,
                hashed_password=get_password_hash(ADMIN_PASSWORD),
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(admin_user)
            await session.flush()
            _print_result("מנהל", "created", f"{ADMIN_EMAIL} / {ADMIN_PASSWORD}")

        # ── חברות + משתמשים ──
        company_profiles: list[CompanyProfile] = []
        for c in COMPANIES:
            result = await session.execute(select(User).where(User.email == c["email"]))
            user = result.scalar_one_or_none()
            if user:
                _print_result("משתמש חברה", "skipped", c["email"])
            else:
                user = User(
                    email=c["email"],
                    hashed_password=get_password_hash(c["password"]),
                    role=UserRole.COMPANY,
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                _print_result(
                    "משתמש חברה", "created", f"{c['email']} / {c['password']}"
                )

            result = await session.execute(
                select(CompanyProfile).where(CompanyProfile.user_id == user.id)
            )
            profile = result.scalar_one_or_none()
            if profile:
                _print_result("פרופיל חברה", "skipped", c["company_name"])
            else:
                profile = CompanyProfile(
                    user_id=user.id,
                    name=c["company_name"],
                    company_id=c["company_id"],
                    address=c["address"],
                    contact_email=c["email"],
                    contact_first_name=c["contact_first_name"],
                    contact_last_name=c["contact_last_name"],
                    contact_mobile_phone=c["contact_mobile_phone"],
                )
                session.add(profile)
                await session.flush()
                _print_result("פרופיל חברה", "created", c["company_name"])

            company_profiles.append(profile)

        # ── משרות ──
        all_jobs: list[Job] = []
        for sector_idx, jobs in enumerate(JOBS_BY_SECTOR):
            offset = _SECTOR_COMPANY_OFFSETS[sector_idx]
            for job_idx, j in enumerate(jobs):
                profile = company_profiles[offset + job_idx]
                result = await session.execute(
                    select(Job).where(
                        Job.company_id == profile.id,
                        Job.title == j["title"],
                    )
                )
                job = result.scalar_one_or_none()
                if job:
                    _print_result("משרה", "skipped", f"{j['title']} ({profile.name})")
                else:
                    job = Job(
                        company_id=profile.id,
                        title=j["title"],
                        short_description=j["short_description"],
                        description=j["description"],
                        requirements=j["requirements"],
                        tags=j["tags"],
                        is_featured=j["is_featured"],
                        location=j["location"],
                        salary_min=j["salary_min"],
                        salary_max=j["salary_max"],
                        status=j["status"],
                    )
                    session.add(job)
                    await session.flush()
                    _print_result(
                        "משרה", "created", f"{j['title']} ({j['status'].value})"
                    )
                all_jobs.append(job)

        # ── מועמדים ──
        storage = get_storage_provider()
        now = datetime.now(timezone.utc)
        created_candidates: list[CandidateProfile] = []
        for i, cand in enumerate(CANDIDATES):
            result = await session.execute(
                select(CandidateProfile).where(CandidateProfile.email == cand["email"])
            )
            existing = result.scalar_one_or_none()
            if existing:
                _print_result("מועמד", "skipped", cand["full_name"])
                created_candidates.append(existing)
                continue

            resume_filename = (
                cand["full_name"].replace(" ", "_").replace("'", "") + ".pdf"
            )
            resume_content = resume_fixtures[i % len(resume_fixtures)].read_bytes()
            resume_path = await storage.upload_file(
                resume_content, f"resumes/{resume_filename}", "application/pdf"
            )
            resume_hash = hashlib.sha256(resume_content).hexdigest()

            registered_at = _days_ago(70 - i * 6)
            user_id: int | None = None
            consent_kwargs: dict = {}
            if cand["registered"]:
                cand_user = User(
                    email=cand["email"],
                    hashed_password=get_password_hash(CANDIDATE_PASSWORD),
                    role=UserRole.CANDIDATE,
                    is_active=True,
                )
                session.add(cand_user)
                await session.flush()
                user_id = cand_user.id
                consent_kwargs = {
                    "consent_given_at": now,
                    "consent_policy_version": CURRENT_PRIVACY_POLICY_VERSION,
                    "consent_ip": _MOCK_CONSENT_IP,
                    "consent_user_agent": _MOCK_USER_AGENT,
                    "tos_accepted_at": now,
                    "tos_version": CURRENT_TERMS_OF_SERVICE_VERSION,
                }
                _print_result(
                    "משתמש מועמד",
                    "created",
                    f"{cand['email']} / {CANDIDATE_PASSWORD}",
                )

            profile = CandidateProfile(
                user_id=user_id,
                full_name=cand["full_name"],
                email=cand["email"],
                phone=cand["phone"],
                linkedin_url=cand["linkedin_url"],
                resume_path=resume_path,
                resume_filename=resume_filename,
                resume_hash=resume_hash,
                **consent_kwargs,
            )
            session.add(profile)
            await session.flush()
            if cand["registered"]:
                await record_audit_event(
                    session,
                    actor_user_id=None,
                    action="candidate.consent",
                    target_type="CandidateProfile",
                    target_id=profile.id,  # type: ignore[arg-type]
                    detail=f"policy_version={CURRENT_PRIVACY_POLICY_VERSION}",
                    created_at=registered_at,
                )
                await record_audit_event(
                    session,
                    actor_user_id=None,
                    action="candidate.terms_accept",
                    target_type="CandidateProfile",
                    target_id=profile.id,  # type: ignore[arg-type]
                    detail=f"terms_version={CURRENT_TERMS_OF_SERVICE_VERSION}",
                    created_at=registered_at,
                )
            _print_result("מועמד", "created", cand["full_name"])
            created_candidates.append(profile)

        # ── מועמדויות ──
        published_jobs = [j for j in all_jobs if j.status == JobStatus.PUBLISHED]
        statuses = [
            ApplicationStatus.NEW,
            ApplicationStatus.APPROVED_BY_ADMIN,
            ApplicationStatus.REJECTED,
            ApplicationStatus.HIRED,
        ]

        for i, candidate in enumerate(created_candidates):
            cand_data = CANDIDATES[i]
            for offset in range(2):
                job_idx = (i + offset) % len(published_jobs)
                job = published_jobs[job_idx]

                result = await session.execute(
                    select(Application).where(
                        Application.job_id == job.id,
                        Application.candidate_id == candidate.id,
                    )
                )
                if result.scalar_one_or_none():
                    _print_result(
                        "מועמדות",
                        "skipped",
                        f"{candidate.full_name} → {job.title}",
                    )
                    continue

                app_status = statuses[(i + offset) % len(statuses)]
                registered_at = _days_ago(70 - i * 6)
                applied_at = registered_at + timedelta(
                    days=3 + offset * 10 + (i % 3) * 4
                )
                # REJECTED only occurs when (i + offset) is even, so vary on i
                # alone to get both rejection paths represented.
                via_review = i % 2 == 0
                status_events, updated_at, admin_notes = _status_history(
                    app_status, applied_at, via_review=via_review
                )

                app = Application(
                    job_id=job.id,
                    candidate_id=candidate.id,
                    status=app_status,
                    admin_notes=admin_notes,
                    service_concept=cand_data["service_concept"],
                    salary_expectations=cand_data["salary_expectations"],
                    strength=cand_data["strength"],
                    growth_area=cand_data["growth_area"],
                    resume_path=candidate.resume_path,
                    resume_filename=candidate.resume_filename,
                    resume_hash=candidate.resume_hash,
                    created_at=applied_at,
                    updated_at=updated_at,
                )
                session.add(app)
                await session.flush()
                for event_at, status_from, status_to in status_events:
                    await record_audit_event(
                        session,
                        actor_user_id=admin_user.id,
                        action="application.status_change",
                        target_type="Application",
                        target_id=app.id,  # type: ignore[arg-type]
                        detail=f"{status_from.value}->{status_to.value}",
                        created_at=event_at,
                    )
                _print_result(
                    "מועמדות",
                    "created",
                    f"{candidate.full_name} → {job.title} [{app_status.value}]",
                )

        await session.commit()

    registered_count = sum(1 for c in CANDIDATES if c["registered"])
    print(f"\n{'─' * 50}")
    print(f"  {'סה"כ':<30} {'נוצר':>8}")
    print(f"  {'─' * 46}")
    print(f"  {'מנהלים':<30} {'1':>8}")
    print(f"  {'חברות':<30} {'20':>8}")
    print(f"  {'משרות':<30} {'15':>8}")
    print(f"  {'מועמדים':<30} {'50':>8}")
    print(f"  {'מועמדים רשומים':<30} {registered_count!s:>8}")
    print(f"  {'מועמדויות':<30} {'~100':>8}")
    print(f"{'─' * 50}")
    print(f"\n🔑 כניסת מנהל:  {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print("🔑 כניסת חברה:  (companyN@example.com / Company123!, N=1..20)")
    print(
        "🔑 כניסת מועמד רשום:  (candidateN@example.com עם N אי-זוגי, 1..49 / "
        f"{CANDIDATE_PASSWORD})"
    )


def main() -> None:
    """נקודת כניסה."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="מחיקת כל נתוני הבדיקה הקיימים לפני ההזרעה",
    )
    parser.add_argument(
        "--resumes-dir",
        metavar="PATH",
        help='ספריית PDF מקומית לקו"ח — עוקפת את קבצי ברירת המחדל',
    )
    parser.add_argument(
        "--resumes-s3-prefix",
        metavar="S3_URI",
        help='קידומת S3 לקו"ח (s3://bucket/prefix/) — מוריד לתיקייה זמנית',
    )
    args = parser.parse_args()
    resume_fixtures = _resolve_resume_fixtures(args.resumes_dir, args.resumes_s3_prefix)

    async def run() -> None:
        await init_db()
        if args.reset:
            await reset(async_session)
        await seed(resume_fixtures)

    asyncio.run(run())


if __name__ == "__main__":
    main()
