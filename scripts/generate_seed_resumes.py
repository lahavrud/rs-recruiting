#!/usr/bin/env python3
"""Generate realistic Hebrew/English resume PDFs for staging seed data.

Run from the repo root:
    uv run --with fpdf2 --with python-bidi scripts/generate_seed_resumes.py

Outputs 10 PDFs to scripts/fixtures/resumes-real/ (or --output-dir).
Upload once to S3 so every staging cycle picks them up:
    aws s3 cp scripts/fixtures/resumes-real/ \\
        s3://<staging-bucket>/seed-fixtures/resumes/ --recursive --exclude "*" --include "*.pdf"

Requirements (not in pyproject.toml — dev-time only):
    fpdf2>=2.8    python-bidi>=0.4

The resumes are intentionally matched to the live job board so the
embedding/matching engine produces meaningful scores for validation.
"""

import argparse
from pathlib import Path

from bidi.algorithm import get_display
from fpdf import FPDF

_HEB_FONT = "/usr/share/fonts/noto/NotoSansHebrew-Regular.ttf"
_HEB_BOLD = "/usr/share/fonts/noto/NotoSansHebrew-Bold.ttf"
_LAT_FONT = "/usr/share/fonts/liberation/LiberationSans-Regular.ttf"
_LAT_BOLD = "/usr/share/fonts/liberation/LiberationSans-Bold.ttf"

_H = get_display  # Apply bidi algorithm before handing to fpdf2


class _CV(FPDF):
    """Single-page A4 Hebrew/English CV layout."""

    def __init__(self) -> None:
        super().__init__()
        self.add_font("Heb", fname=_HEB_FONT)
        self.add_font("HebB", fname=_HEB_BOLD)
        self.add_font("Lat", fname=_LAT_FONT)
        self.add_font("LatB", fname=_LAT_BOLD)
        self.set_margins(14, 14, 14)

    def header_block(self, heb_name: str, lat_title: str, contact: str) -> None:
        self.set_font("HebB", size=20)
        self.cell(0, 12, _H(heb_name), align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_font("LatB", size=12)
        self.cell(0, 8, lat_title, align="L", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Lat", size=10)
        self.cell(0, 7, contact, align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_draw_color(180, 160, 140)
        self.line(14, self.get_y(), 196, self.get_y())
        self.ln(4)

    def section(self, heb_title: str) -> None:
        self.ln(3)
        self.set_font("HebB", size=12)
        self.set_fill_color(228, 222, 215)
        self.cell(
            0, 8, _H(heb_title), align="R", fill=True, new_x="LMARGIN", new_y="NEXT"
        )
        self.ln(2)

    def hline(self, text: str, size: int = 10, bold: bool = False) -> None:
        self.set_font("HebB" if bold else "Heb", size=size)
        self.cell(0, 6, _H(text), align="R", new_x="LMARGIN", new_y="NEXT")

    def lline(self, text: str, size: int = 10, bold: bool = False) -> None:
        self.set_font("LatB" if bold else "Lat", size=size)
        self.cell(0, 6, text, align="L", new_x="LMARGIN", new_y="NEXT")

    def job(
        self, lat_title: str, lat_company: str, period: str, heb_bullets: list[str]
    ) -> None:
        self.set_font("LatB", size=11)
        self.cell(
            0,
            7,
            f"{lat_title}  |  {lat_company}",
            align="L",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_font("Lat", size=9)
        self.cell(0, 6, period, align="L", new_x="LMARGIN", new_y="NEXT")
        for bullet in heb_bullets:
            self.set_font("Heb", size=9)
            self.cell(6, 6, "")
            self.cell(0, 6, _H(f"• {bullet}"), align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def skill(self, heb_label: str, lat_value: str) -> None:
        w = self.get_string_width(_H(heb_label)) + 6
        self.set_font("HebB", size=9)
        self.cell(w, 6, _H(heb_label), align="R")
        self.set_font("Lat", size=9)
        self.cell(0, 6, lat_value, align="L", new_x="LMARGIN", new_y="NEXT")


def _make_pdf(profile: dict) -> bytes:
    cv = _CV()
    cv.add_page()

    cv.header_block(profile["heb_name"], profile["lat_title"], profile["contact"])

    cv.section("סיכום מקצועי")
    cv.hline(profile["summary"], size=9)

    cv.section("ניסיון תעשייתי")
    for exp in profile["experience"]:
        cv.job(exp["lat_title"], exp["lat_company"], exp["period"], exp["heb_bullets"])

    cv.section("כישורים ומיומנויות")
    for heb_label, lat_val in profile["skills"]:
        cv.skill(heb_label, lat_val)

    cv.section("השכלה")
    for edu in profile["education"]:
        cv.hline(edu, size=9)

    import io

    buf = io.BytesIO()
    cv.output(buf)
    return buf.getvalue()


# ── Resume profiles ───────────────────────────────────────────────────────────
# Each profile matches one or more live job postings so the embedding engine
# produces meaningful match scores. Profiles are ordered by seniority / domain.

PROFILES: list[dict] = [
    {
        "filename": "yossi_maman_facilities_manager.pdf",
        "heb_name": "יוסי ממן",
        "lat_title": "Senior Facilities Manager",
        "contact": "yossi.maman@gmail.com  |  052-000-0001  |  Tel Aviv",
        "summary": (
            "מנהל מתחם בכיר עם 10 שנות ניסיון בניהול מגדלי משרדים ומתחמים מסחריים. "
            "אחריות מלאה על תפעול מערכות מבנה, ניהול תקציבים, קשרי שוכרים ופיקוח על צוותים רב-תחומיים."
        ),
        "experience": [
            {
                "lat_title": "Facilities Manager",
                "lat_company": "Azrieli Group – Commercial Tower, TLV",
                "period": "2019 – present",
                "heb_bullets": [
                    "ניהול מגדל משרדים של 30 קומות ו-200 שוכרים בתל אביב",
                    "פיקוח על תקציב שנתי של 8 מיליון ₪ לתפעול ואחזקה",
                    "ניהול 40 עובדים: אחזקה, ניקיון, אבטחה, קבלת קהל",
                    "הובלת פרויקטי שיפוץ מערכות מיזוג וחשמל",
                ],
            },
            {
                "lat_title": "Assistant Facilities Manager",
                "lat_company": "Gav-Yam Lands – Herzliya Pituach Park",
                "period": "2015 – 2019",
                "heb_bullets": [
                    "ניהול מתחם 15 בניינים עם 80 שוכרים",
                    "שיפור שביעות רצון שוכרים מ-72% ל-91% תוך שנתיים",
                    "תפעול מערכות BMS, HVAC, ספרינקלרים וגילוי אש",
                ],
            },
            {
                "lat_title": "Building Technician",
                "lat_company": "Amot Investments",
                "period": "2012 – 2015",
                "heb_bullets": [
                    "אחזקה שוטפת ומונעת של מערכות מבנה",
                    "מענה לקריאות שבר ותיאום קבלנים חיצוניים",
                ],
            },
        ],
        "skills": [
            ("מערכות", "BMS (Schneider EcoStruxure), HVAC, CCTV, Access Control"),
            ("תוכנות", "SAP PM, CAFM, AutoCAD, Microsoft Office 365"),
            ("שפות", "Hebrew – native | English – fluent | Arabic – conversational"),
            ("הסמכות", "Certified Facility Manager (IFMA), Technion Extension 2018"),
        ],
        "education": [
            "הנדסאי בניין – מכון טכנולוגי חולון, 2012",
            "הסמכת ניהול מתקנים – IFMA Israel Chapter, 2018",
        ],
    },
    {
        "filename": "rinnat_shapira_property_manager.pdf",
        "heb_name": "רינת שפירא",
        "lat_title": "Property Manager – Commercial & Mixed-Use",
        "contact": "rinnat.shapira@gmail.com  |  054-000-0002  |  Herzliya",
        "summary": (
            'מנהלת נכסים עם 7 שנות ניסיון בחברות נדל"ן מניב. '
            "ניהול שוטף של בנייני משרדים ומסחר, קשרי שוכרים, חוזי שכירות ובקרת ספקים. "
            "תודעת שירות גבוהה ויכולת פתרון בעיות מורכבות מול דיירים עסקיים."
        ),
        "experience": [
            {
                "lat_title": "Property Manager",
                "lat_company": "Bayside Land Corporation – Office Park Herzliya",
                "period": "2020 – present",
                "heb_bullets": [
                    "ניהול שוטף של מתחם משרדים ומסחר בהרצליה פיתוח",
                    'ניהול קשרי שוכרים מול 60+ חברות הייטק, משרדי עו"ד ופיננסים',
                    "טיפול בחוזי שכירות, חידושים, פינויים ושינויי ייעוד",
                    "פיקוח על תחזוקה, ניקיון, אבטחה וקבלני שירות",
                ],
            },
            {
                "lat_title": "Junior Property Manager",
                "lat_company": "Mivne Real Estate",
                "period": "2016 – 2020",
                "heb_bullets": [
                    "ניהול 4 נכסים בתל אביב עם 120 יחידות שכירות",
                    "הכנת דוחות ניהול חודשיים לבעלי הנכסים",
                    "תיאום בין שוכרים לספקי שירות לצמצום זמני תגובה",
                ],
            },
        ],
        "skills": [
            (
                "ניהול נכסים",
                "Lease administration, Tenant relations, Vendor management",
            ),
            ("תוכנות", "Yardi Voyager, Priority ERP, Microsoft Office 365"),
            (
                "שפות",
                "Hebrew – native | English – high level | Russian – conversational",
            ),
            ("רישיונות", "Real Estate License – Israel Ministry of Justice, 2017"),
        ],
        "education": [
            "תואר ראשון בניהול עסקים (מנהל עסקים) – אוניברסיטת חיפה, 2016",
            'מתמחה בנדל"ן מסחרי – לשכת שמאי המקרקעין, 2017',
        ],
    },
    {
        "filename": "shlomo_avraham_chief_electrician.pdf",
        "heb_name": "שלמה אברהם",
        "lat_title": "Chief Electrician & Technical Team Lead",
        "contact": "shlomo.avraham@gmail.com  |  050-000-0003  |  Tel Aviv",
        "summary": (
            "ראש צוות טכני ו-חשמלאי ראשי מוסמך עם 8 שנות ניסיון בחברות הייטק ומגדלי משרדים. "
            "ניהול ישיר של צוותי אחזקה, תכנית אחזקה מונעת שנתית, ועמידה בדרישות רגולטוריות ואישורי רשויות."
        ),
        "experience": [
            {
                "lat_title": "Technical Team Lead / Chief Electrician",
                "lat_company": "Check Point Software Technologies – Campus TLV",
                "period": "2020 – present",
                "heb_bullets": [
                    "ניהול צוות של 6 טכנאים: חשמל, מיזוג, אינסטלציה",
                    "אחריות על כלל מערכות החשמל במתח נמוך וגבוה בקמפוס של 4 מבנים",
                    "בקרה ומעקב על תכנית אחזקה מונעת שנתית",
                    "אחריות על אישורי כיבוי אש, בדיקות מעליות ואישורי משרד האנרגיה",
                    "ניהול פרויקטים: שדרוג לוחות חשמל, החלפת מערכות UPS",
                ],
            },
            {
                "lat_title": "Senior Electrician",
                "lat_company": "Electra FM – Hi-Tech Sites",
                "period": "2016 – 2020",
                "heb_bullets": [
                    "אחזקה חשמלית באתרי הייטק: Akamai, Microsoft Israel",
                    "ביצוע בדיקות תקופתיות: תרמוגרפיה, בדיקות בידוד",
                    "עבודה מול קבלני משנה וספקים מורשים",
                ],
            },
            {
                "lat_title": "Electrician",
                "lat_company": "Delek Group – Industrial Facilities",
                "period": "2014 – 2016",
                "heb_bullets": [
                    "התקנה ואחזקת מערכות חשמל תעשייתיות",
                    "מענה לקריאות שבר 24/7",
                ],
            },
        ],
        "skills": [
            (
                "רישיונות",
                "Chief Electrician License (Rishum Rishon) – Ministry of Energy",
            ),
            (
                "מערכות",
                "HV/LV switchgear, UPS, generators, fire alarm, BMS integration",
            ),
            ("תוכנות", "AutoCAD Electrical, Microsoft Office, Maintimizer CMMS"),
            ("שפות", "Hebrew – native | English – good working level"),
        ],
        "education": [
            "הנדסאי חשמל – ORT Singalovsky College, Tel Aviv, 2014",
            "רישיון חשמלאי ראשי – משרד האנרגיה, 2019",
        ],
    },
    {
        "filename": "amir_golan_maintenance_electrician.pdf",
        "heb_name": "עמיר גולן",
        "lat_title": "Maintenance Electrician – HVAC & Building Systems",
        "contact": "amir.golan@gmail.com  |  058-000-0004  |  Kfar Saba",
        "summary": (
            "חשמלאי אחזקה מוסמך עם 5 שנות ניסיון בתחזוקת מערכות חשמל ומיזוג אוויר. "
            "ניסיון בעבודה באתרי הייטק, מרכזי לוגיסטיקה ובנייני משרדים. "
            "זמינות מלאה לכוננות ומענה לקריאות שבר."
        ),
        "experience": [
            {
                "lat_title": "Maintenance Electrician",
                "lat_company": "Elbit Systems – Haifa & Herzliya Sites",
                "period": "2021 – present",
                "heb_bullets": [
                    "אחזקה שוטפת ומונעת של מערכות חשמל ומיזוג אוויר",
                    "ביצוע תכנית PM שנתית: בדיקות חשמל, סרוויס מזגנים",
                    "מענה לקריאות שבר ותיקון תקלות בשעות כוננות",
                    "ביצוע עבודות חשמל קטנות: נקודות תאורה, שקעים, לוחות חשמל",
                ],
            },
            {
                "lat_title": "Electrician & HVAC Technician",
                "lat_company": "Supergas / Strauss Group – Industrial Sites",
                "period": "2018 – 2021",
                "heb_bullets": [
                    "תחזוקת מערכות מיזוג תעשייתיות: מסוקי צינון, מערכות VRF",
                    "עבודות חשמל תעשייתיות: מנועים, בקרים, משאבות",
                    "אחריות על ציוד כיבוי אש ומערכת גילוי גז",
                ],
            },
        ],
        "skills": [
            ("רישיונות", "Electrician License (Rishum Sheni) | HVAC Certification"),
            ("מערכות", "VRF systems, chillers, UPS, fire alarm, access control"),
            ("ציוד", "Multimeter, thermal camera, cable tester, oscilloscope"),
            ("שפות", "Hebrew – native | English – basic reading/writing"),
        ],
        "education": [
            "חשמלאי מוסמך – מכללת עמל, כפר סבא, 2018",
            "הסמכת מיזוג אוויר – מכון בר-לב, 2019",
        ],
    },
    {
        "filename": "dana_levi_technical_coordinator.pdf",
        "heb_name": "דנה לוי",
        "lat_title": "Technical Coordinator – Facilities Management",
        "contact": "dana.levi@gmail.com  |  053-000-0005  |  Tel Aviv",
        "summary": (
            "מתאמת טכנית עם 4 שנות ניסיון בתחום ניהול מתקנים בחברות הייטק. "
            "ניסיון בניהול ספקים, עבודה עם מערכות CMMS, מעקב הזמנות רכש ותקציבים. "
            "שפת אנגלית ברמה גבוהה מאוד – כולל ניהול שיחות וכתיבה מקצועית."
        ),
        "experience": [
            {
                "lat_title": "Technical Coordinator / FM Coordinator",
                "lat_company": "Meta – Israel Engineering Office, TLV",
                "period": "2022 – present",
                "heb_bullets": [
                    "תיאום פעילות ספקים ובקרת איכות שירות לאתרי Meta בישראל",
                    "ניהול מערכת CMMS (ServiceNow FM): פתיחת, מעקב וסגירת קריאות שירות",
                    "מעקב על הזמנות רכש, חשבוניות ועמידה בתקציב שנתי",
                    'עבודה מול הנהלת האתר ומשרד ראשי בארה"ב – בעיקר באנגלית',
                    "אחריות על תכנית PM: תיאום ביקורות שנתיות ואישורי רגולציה",
                ],
            },
            {
                "lat_title": "Facilities Coordinator",
                "lat_company": "CBRE – Israel Outsourced FM",
                "period": "2020 – 2022",
                "heb_bullets": [
                    "ניהול ספקי FM עבור לקוחות גלובליים: Intel, Booking.com",
                    "הכנת דוחות SLA ומדדי ביצוע חודשיים",
                    "תיאום עבודות שיפוץ ושדרוג מערכות עם בעלי הנכסים",
                ],
            },
        ],
        "skills": [
            ("מערכות CMMS", "ServiceNow FM, Maximo, Archibus, SAP PM"),
            ("תוכנות", "Microsoft Office 365, Teams, SharePoint, Power BI"),
            ("שפות", "Hebrew – native | English – excellent (C1) | French – basic"),
            ("הסמכות", "IWFM Associate Member | OSHA 30-Hour General Industry"),
        ],
        "education": [
            "תואר ראשון בניהול מלונאות ואירועים – מכללת רופין, 2020",
            "קורס ניהול מתקנים – IFMA Israel, 2021",
        ],
    },
    {
        "filename": "alon_cohen_maintenance_manager.pdf",
        "heb_name": "אלון כהן",
        "lat_title": "Maintenance Manager – Commercial Complexes",
        "contact": "alon.cohen@gmail.com  |  052-000-0006  |  Ramat HaHayal, TLV",
        "summary": (
            "מנהל אחזקה עם 6 שנות ניסיון בניהול תפעול ואחזקה במתחמים מסחריים ועסקיים. "
            "הנדסאי חשמל מוסמך עם ניסיון בניהול ספקים, לקוחות עסקיים ופיקוח על צוות טכני."
        ),
        "experience": [
            {
                "lat_title": "Maintenance Manager",
                "lat_company": "Nofar Energy – Ramat HaHayal Business Park",
                "period": "2021 – present",
                "heb_bullets": [
                    "ניהול תפעול ואחזקה של מתחם עסקים ומסחר בן 12 בניינים",
                    "פיקוח על צוות 8 טכנאים: חשמל, מיזוג, אינסטלציה",
                    "ניהול ספקים ותיאום עבודות קבלן מול שוכרי משרדים וחנויות",
                    "בקרת עלויות ועמידה בתקציב שנתי של 3.5 מיליון ₪",
                ],
            },
            {
                "lat_title": "Technical Supervisor",
                "lat_company": "Electra Real Estate",
                "period": "2017 – 2021",
                "heb_bullets": [
                    "פיקוח טכני על 3 מתחמי משרדים בגוש דן",
                    "ביצוע תכנית אחזקה מונעת ואחזקת מבנה שוטפת",
                    "ניהול ממשק מול לקוחות עסקיים וחברות ניהול",
                ],
            },
        ],
        "skills": [
            ("מקצועי", "Electrical systems, HVAC maintenance, BMS monitoring"),
            ("ניהולי", "Budget control, vendor negotiation, team supervision"),
            ("תוכנות", "Microsoft Office, Maintimizer, Priority"),
            ("שפות", "Hebrew – native | English – intermediate"),
        ],
        "education": [
            "הנדסאי חשמל – מכון טכנולוגי בת-ים, 2017",
        ],
    },
    {
        "filename": "merav_mizrahi_office_manager.pdf",
        "heb_name": "מירב מזרחי",
        "lat_title": "Senior Office Manager – Global Technology Companies",
        "contact": "merav.mizrahi@gmail.com  |  054-000-0007  |  Rosh HaAyin",
        "summary": (
            "מנהלת משרד בכירה עם 9 שנות ניסיון בחברות גלובליות וסביבת עבודה רב-לאומית. "
            "ניסיון בתמיכה מנהלתית להנהלה בכירה, ארגון נסיעות עסקיות בינלאומיות, "
            'ניהול ביקורים בכירים ועבודה שוטפת מול מטות חברה בחו"ל. אנגלית ברמה מצוינת.'
        ),
        "experience": [
            {
                "lat_title": "Senior Office Manager / EA to VP",
                "lat_company": "Ericsson Israel – Rosh HaAyin",
                "period": "2019 – present",
                "heb_bullets": [
                    'תמיכה מנהלתית לסמנכ"ל ישראל ולצוות הנהלה מקומי של 12 מנהלים',
                    "ארגון נסיעות עסקיות: טיסות, מלונות, ויזות לכ-30 נסיעות בשנה",
                    "ניהול יומן, תיאום פגישות בינלאומיות ופגישות ועד החברה",
                    "ארגון ביקורי הנהלה בכירה ממטה סטוקהולם ומינוי ישיבות ישות משפטית",
                    "ניהול ספקים, הזמנות רכש ובקרת תקציב משרד",
                ],
            },
            {
                "lat_title": "Office Manager",
                "lat_company": "Nokia Networks Israel – Airport City",
                "period": "2015 – 2019",
                "heb_bullets": [
                    "ניהול שוטף של משרד בן 80 עובדים",
                    'תיאום מול ספקים, עו"ד, רואי חשבון ורשויות',
                    "תמיכה לפרויקטים HR: גיוס, קליטה ואירועי חברה",
                ],
            },
        ],
        "skills": [
            ("שפות", "Hebrew – native | English – excellent (C1) | Swedish – basic"),
            ("תוכנות", "Microsoft Office 365, SAP Concur, Outlook, SharePoint, Zoom"),
            (
                "מיומנויות",
                "Executive support, international travel management, events, procurement",
            ),
        ],
        "education": [
            "מזכירות ומינהל עסקים – מכללת רמות, תל אביב, 2015",
        ],
    },
    {
        "filename": "tomer_peretz_business_development.pdf",
        "heb_name": "תומר פרץ",
        "lat_title": "Business Development Manager – Facilities & Real Estate",
        "contact": "tomer.peretz@gmail.com  |  050-000-0008  |  Bnei Brak",
        "summary": (
            'מנהל פיתוח עסקי ומכירות B2B עם 5 שנות ניסיון בתחום שירותי הניהול והנדל"ן המסחרי. '
            "מיומנות מוכחת באיתור לקוחות חדשים, ניהול משא ומתן וסגירת חוזים ארוכי טווח. "
            'ניסיון בעבודה מול יזמים, חברות נדל"ן מניב וחברות ניהול מבנים.'
        ),
        "experience": [
            {
                "lat_title": "Business Development Manager",
                "lat_company": "Superbus FM – Facilities Management Company",
                "period": "2021 – present",
                "heb_bullets": [
                    "איתור והובלת עסקאות B2B עם מגדלי משרדים ומתחמים מסחריים",
                    "סגירת חוזי ניהול מבנים בהיקף שנתי של 12 מיליון ₪",
                    'פנייה יזומה ליזמים וחברות נדל"ן מניב ברחבי גוש דן',
                    'הצגות מכירה, הכנת הצעות מחיר ומו"מ מול הנהלות בכירות',
                ],
            },
            {
                "lat_title": "Sales Representative – Commercial Real Estate",
                "lat_company": "CBRE Israel",
                "period": "2018 – 2021",
                "heb_bullets": [
                    "שיווק נכסים מסחריים: השכרת משרדים, מחסנים ומתחמי לוגיסטיקה",
                    "ניהול קשרי לקוחות ארוכי טווח מול חברות Fortune 500 בישראל",
                    "חציית יעד מכירות שנתי ב-30% בשנת 2020",
                ],
            },
        ],
        "skills": [
            (
                "מכירות",
                "B2B sales, cold outreach, proposal writing, contract negotiation",
            ),
            (
                "תחום",
                "Facilities management, commercial real estate, property management",
            ),
            (
                "תוכנות",
                "Salesforce CRM, HubSpot, Microsoft Office, LinkedIn Sales Navigator",
            ),
            ("שפות", "Hebrew – native | English – fluent | Arabic – conversational"),
        ],
        "education": [
            "תואר ראשון בכלכלה וניהול – אוניברסיטת בר-אילן, 2018",
        ],
    },
    {
        "filename": "orit_biton_luxury_residential.pdf",
        "heb_name": "אורית ביטון",
        "lat_title": "Luxury Residential Complex Manager",
        "contact": "orit.biton@gmail.com  |  058-000-0009  |  Tel Aviv",
        "summary": (
            "מנהלת מתחם מגורים יוקרתי עם 7 שנות ניסיון בניהול בנייני יוקרה בתל אביב. "
            "מוניטין מצוין בשירות ברמה גבוהה, ניהול ועד בית, "
            "ותיאום מול דיירים בעלי צרכים מורכבים. זמינות 24/7 לטיפול בחירום."
        ),
        "experience": [
            {
                "lat_title": "Residential Complex Manager",
                "lat_company": "Rubinstein Premium Residences – Rothschild Blvd, TLV",
                "period": "2020 – present",
                "heb_bullets": [
                    "ניהול שני מגדלי מגורים יוקרתיים: 120 יחידות, 300 דיירים",
                    'שירות אישי לדיירים בכירים: נציגי שגרירויות, מנכ"לים ובינלאומיים',
                    "ניהול ועד הבית, ישיבות, תקציב וניהול חשבונות",
                    "פיקוח על אחזקה, ניקיון, אבטחה ולוגיסטיקה שוטפת",
                    "טיפול בחירומים: נזילות, תקלות מעלית, מצבי חירום כלליים",
                ],
            },
            {
                "lat_title": "Building Manager",
                "lat_company": "Danya Cebus – Upscale Residential Projects",
                "period": "2016 – 2020",
                "heb_bullets": [
                    "ניהול בנייני מגורים חדשים בתקופת הכנסת דיירים",
                    "קבלת דיירים, ביצוע סיורי מסירה ותיעוד ליקויים",
                    "ניהול ספקים: מעליות, גנרטורים, גינון ובריכות שחייה",
                ],
            },
        ],
        "skills": [
            (
                "שירות",
                "High-end resident relations, 24/7 availability, crisis management",
            ),
            (
                "ניהולי",
                "HOA management, budgeting, vendor contracts, maintenance oversight",
            ),
            ("תוכנות", "Buildium, Monday.com, Microsoft Office"),
            ("שפות", "Hebrew – native | English – fluent | French – intermediate"),
        ],
        "education": [
            "מנהל עסקים (B.A) – המכללה האקדמית תל-אביב יפו, 2016",
            "קורס ניהול בתים משותפים – לשכת שמאי המקרקעין, 2017",
        ],
    },
    {
        "filename": "guy_azoulay_building_systems_engineer.pdf",
        "heb_name": "גיא אזולאי",
        "lat_title": "Building Systems Engineer – BMS & Energy Management",
        "contact": "guy.azoulay@gmail.com  |  052-000-0010  |  Herzliya",
        "summary": (
            "מהנדס מערכות בניין עם 9 שנות ניסיון ב-BMS, ניהול אנרגיה ומערכות HVAC מורכבות. "
            "ניסיון מעמיק במערכות Schneider EcoStruxure ו-Siemens Desigo. "
            "הובלת פרויקטי אינטגרציה ואופטימיזציית צריכת אנרגיה במגדלי משרדים ובאתרי הייטק."
        ),
        "experience": [
            {
                "lat_title": "Building Systems Engineer / Technical Lead",
                "lat_company": "Johnson Controls Israel – Key Accounts",
                "period": "2019 – present",
                "heb_bullets": [
                    "הובלת פרויקטי BMS: התקנה, אינטגרציה ותפעול מערכות Schneider ו-Siemens",
                    "ניהול טכני של אתרי לקוח: Deloitte, Bank Leumi, WeWork Israel",
                    "אופטימיזציית צריכת אנרגיה: חיסכון ממוצע 18% לשנה ללקוח",
                    "הכשרת צוותי תפעול פנים-ארגוניים ב-BMS וניטור מרחוק",
                ],
            },
            {
                "lat_title": "HVAC & BMS Engineer",
                "lat_company": "Tadiran Air Control – Commercial Projects",
                "period": "2015 – 2019",
                "heb_bullets": [
                    "תכנון והתקנת מערכות מיזוג מרכזיות ומסוקי צינון",
                    "אינטגרציה של מערכות BMS למערכות HVAC, חשמל וגילוי אש",
                    "עבודה מול קבלני מבנה, חברות בנייה ומשרדי ייעוץ",
                ],
            },
            {
                "lat_title": "HVAC Technician",
                "lat_company": "Electra Consumer Products",
                "period": "2013 – 2015",
                "heb_bullets": [
                    "התקנה ותחזוקת מערכות מיזוג תעשייתיות ומסחריות",
                ],
            },
        ],
        "skills": [
            (
                "BMS",
                "Schneider EcoStruxure, Siemens Desigo CC, Honeywell Building Manager",
            ),
            ("HVAC", "Chillers, AHUs, VRF systems, cooling towers, precision AC"),
            ("אנרגיה", "ISO 50001, energy auditing, sub-metering, demand response"),
            ("שפות", "Hebrew – native | English – fluent | French – basic"),
            ("הסמכות", "Schneider EcoStruxure Certified | LEED Green Associate"),
        ],
        "education": [
            "הנדסאי מכונות – מכון טכנולוגי חולון (HIT), 2013",
            "תואר שני בהנדסת אנרגיה – אוניברסיטת בן-גוריון, 2018",
        ],
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="scripts/fixtures/resumes-real",
        help="Directory to write PDFs into (default: scripts/fixtures/resumes-real)",
    )
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for profile in PROFILES:
        data = _make_pdf(profile)
        dest = out / profile["filename"]
        dest.write_bytes(data)
        print(f"  wrote {dest}  ({len(data) // 1024} KB)")

    print(f"\nDone — {len(PROFILES)} PDFs in {out}/")
    print("\nUpload to S3:")
    print(
        f"  aws s3 cp {out}/ "
        "s3://<staging-bucket>/seed-fixtures/resumes/ --recursive --include '*.pdf'"
    )


if __name__ == "__main__":
    main()
