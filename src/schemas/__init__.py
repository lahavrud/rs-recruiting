"""Domain-scoped Pydantic schemas — re-exported for backward compatibility.

Import from the domain modules directly for new code:
  from src.schemas.auth import UserRead
  from src.schemas.jobs import JobRead
  ...

All existing ``from src.schemas import X`` statements continue to work
through this barrel.
"""

from src.schemas.audit import AuditLogRead, CandidateActivityEvent
from src.schemas.auth import (
    AccessTokenResponse,
    CandidateRegisterRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    ResendActivationRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserRead,
    _validate_password_complexity,
)
from src.schemas.candidates import (
    ApplicationCreate,
    ApplicationNotesUpdate,
    ApplicationRead,
    ApplicationStatusUpdate,
    ApplicationUpdate,
    ApplicationWithDetails,
    CandidateApplicationCompany,
    CandidateApplicationDetail,
    CandidateApplicationJobDetail,
    CandidateApplicationJobSummary,
    CandidateApplicationListItem,
    CandidateApplicationMyAnswers,
    CandidateApplicationResumeMeta,
    CandidateJobMatchRead,
    CandidateMeRead,
    CandidateMeUpdate,
    CandidateProfileCreate,
    CandidateProfileRead,
    JobCandidateMatchRead,
)
from src.schemas.companies import (
    ActiveCompanyRead,
    ApprovedCompanyRead,
    CompanyDataExport,
    CompanyProfileAdminCreate,
    CompanyProfileAdminUpdate,
    CompanyProfileCreate,
    CompanyProfileRead,
    PendingCompanyRead,
    UserCreate,
    UserWithCompanyRead,
)
from src.schemas.invites import (
    InviteMetadataPublic,
    InviteTokenCreate,
    InviteTokenRead,
)
from src.schemas.jobs import (
    JOB_REQ_MAX_COUNT,
    JOB_REQ_MIN_COUNT,
    JOB_REQ_TEXT_MAX,
    JOB_SHORT_DESC_MAX,
    JOB_TAG_MAX_COUNT,
    JOB_TAG_MAX_LEN,
    JobAdminCreate,
    JobAdminUpdate,
    JobContactEmailRequest,
    JobCreate,
    JobPublicRead,
    JobRead,
    JobRequirementItem,
    JobUpdate,
)

__all__ = [
    # auth
    "AccessTokenResponse",
    "CandidateRegisterRequest",
    "ChangePasswordRequest",
    "ForgotPasswordRequest",
    "LoginRequest",
    "RefreshRequest",
    "ResendActivationRequest",
    "ResetPasswordRequest",
    "TokenResponse",
    "UserRead",
    "_validate_password_complexity",
    # companies
    "ActiveCompanyRead",
    "ApprovedCompanyRead",
    "CompanyDataExport",
    "CompanyProfileAdminCreate",
    "CompanyProfileAdminUpdate",
    "CompanyProfileCreate",
    "CompanyProfileRead",
    "PendingCompanyRead",
    "UserCreate",
    "UserWithCompanyRead",
    # jobs
    "JOB_REQ_MAX_COUNT",
    "JOB_REQ_MIN_COUNT",
    "JOB_REQ_TEXT_MAX",
    "JOB_SHORT_DESC_MAX",
    "JOB_TAG_MAX_COUNT",
    "JOB_TAG_MAX_LEN",
    "JobAdminCreate",
    "JobAdminUpdate",
    "JobContactEmailRequest",
    "JobCreate",
    "JobPublicRead",
    "JobRead",
    "JobRequirementItem",
    "JobUpdate",
    # candidates
    "ApplicationCreate",
    "ApplicationNotesUpdate",
    "ApplicationRead",
    "ApplicationStatusUpdate",
    "ApplicationUpdate",
    "ApplicationWithDetails",
    "CandidateApplicationCompany",
    "CandidateApplicationDetail",
    "CandidateApplicationJobDetail",
    "CandidateApplicationJobSummary",
    "CandidateApplicationListItem",
    "CandidateApplicationMyAnswers",
    "CandidateApplicationResumeMeta",
    "CandidateJobMatchRead",
    "CandidateMeRead",
    "CandidateMeUpdate",
    "CandidateProfileCreate",
    "CandidateProfileRead",
    "JobCandidateMatchRead",
    # invites
    "InviteMetadataPublic",
    "InviteTokenCreate",
    "InviteTokenRead",
    # audit
    "AuditLogRead",
    "CandidateActivityEvent",
]
