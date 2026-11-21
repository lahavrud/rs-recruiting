"""Security emails for MFA events (#1177).

Every change to a user's second factor, and every sign that someone else holds
their password, is emailed to the account owner: it is the one channel an
attacker who enrolled first, or who found a recovery code, does not control.

Queued through the outbox, so callers must be inside ``transactional()``; the
email commits (or rolls back) with the event it reports.
"""

from datetime import datetime, timezone
from enum import Enum
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.tasks import queue_email
from rs_shared.templates.email import build_mfa_security_notice_html

_TZ = ZoneInfo("Asia/Jerusalem")


class MfaEvent(str, Enum):
    ENROLLED = "enrolled"
    RECOVERY_CODE_USED = "recovery_code_used"
    RECOVERY_CODES_REGENERATED = "recovery_codes_regenerated"
    LOCKED = "locked"
    RESET = "reset"


_TITLES: dict[MfaEvent, str] = {
    MfaEvent.ENROLLED: "אימות דו-שלבי הופעל",
    MfaEvent.RECOVERY_CODE_USED: "נכנסתם עם קוד שחזור",
    MfaEvent.RECOVERY_CODES_REGENERATED: "נוצרו קודי שחזור חדשים",
    MfaEvent.LOCKED: "ניסיונות כניסה חשודים לחשבון",
    MfaEvent.RESET: "האימות הדו-שלבי אופס",
}

_MESSAGES: dict[MfaEvent, str] = {
    MfaEvent.ENROLLED: (
        "אימות דו-שלבי הופעל בחשבון שלכם. מעכשיו כל כניסה תדרוש גם קוד מאפליקציית"
        " האימות, וכל שאר החיבורים לחשבון נותקו."
    ),
    MfaEvent.RECOVERY_CODE_USED: (
        "בוצעה כניסה לחשבון עם קוד שחזור. נותרו {remaining} קודים שלא נוצלו;"
        " אם נשארו מעט, צרו סדרה חדשה בעמוד הפרופיל."
    ),
    MfaEvent.RECOVERY_CODES_REGENERATED: (
        "נוצרה סדרה חדשה של קודי שחזור לחשבון שלכם. הקודים הקודמים כבר לא תקפים."
    ),
    MfaEvent.LOCKED: (
        "מישהו הזין את הסיסמה הנכונה לחשבון שלכם ואחריה כמה קודי אימות שגויים,"
        " ולכן הכניסה ננעלה זמנית. אם זה לא הייתם אתם, הסיסמה שלכם כנראה דלפה."
    ),
    MfaEvent.RESET: (
        "האימות הדו-שלבי בחשבון שלכם אופס וכל החיבורים נותקו. בכניסה הבאה"
        " תתבקשו להגדיר אותו מחדש."
    ),
}


async def notify_mfa_event(
    session: AsyncSession,
    email: str,
    event: MfaEvent,
    *,
    ip: str | None = None,
    remaining: int | None = None,
) -> None:
    """Queue the owner's security email for ``event``."""
    title = _TITLES[event]
    message = _MESSAGES[event].format(remaining=remaining)
    occurred_at = datetime.now(timezone.utc).astimezone(_TZ).strftime("%d/%m/%Y %H:%M")
    when = f"{occurred_at} (שעון ישראל)"
    plain = (
        f"{message}\n{when}{f' · {ip}' if ip else ''}\nלא אתם? החליפו מיד את הסיסמה."
    )
    await queue_email(
        session,
        to=email,
        subject=f"{title} — RS Recruiting",
        body=plain,
        html_body=build_mfa_security_notice_html(
            title=title, message=message, occurred_at=when, ip=ip
        ),
    )
