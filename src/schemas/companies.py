"""Company and user registration schemas.

UserCreate lives here (not auth) because it bundles CompanyProfileCreate —
company registration is the only path that creates a User in this system.
"""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.schemas.auth import UserRead, _validate_password_complexity
from src.schemas.jobs import JobRead


class CompanyProfileCreate(BaseModel):
    """Schema for creating a company profile."""

    name: str = Field(..., max_length=100)
    company_id: str  # ח.פ — 9-digit Israeli company registration number
    address: str = Field(..., max_length=200)
    contact_first_name: str = Field(..., min_length=2, max_length=100)
    contact_last_name: str = Field(..., min_length=2, max_length=100)
    contact_mobile_phone: str
    contact_landline_phone: str | None = Field(None, max_length=20)

    @field_validator("company_id")
    @classmethod
    def validate_company_id(cls, v: str) -> str:
        if not re.fullmatch(r"\d{9}", v):
            raise ValueError("Company ID must be exactly 9 digits")
        return v

    @field_validator("contact_mobile_phone")
    @classmethod
    def validate_mobile_phone(cls, v: str) -> str:
        if not re.fullmatch(r"05[0-9]\d{7}", v):
            raise ValueError(
                "Mobile phone must be a valid Israeli mobile number (05X-XXXXXXX)"
            )
        return v


class UserCreate(BaseModel):
    """Schema for creating a user (registration)."""

    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    company_profile: CompanyProfileCreate

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_complexity(v)


class CompanyProfileRead(BaseModel):
    """Schema for reading company profile data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    name: str
    logo_url: str | None
    company_id: str
    address: str
    contact_email: EmailStr
    contact_first_name: str
    contact_last_name: str
    contact_mobile_phone: str
    contact_landline_phone: str | None
    agreement_signed_at: datetime | None
    agreement_signature_url: str | None
    contract_pdf_url: str | None
    privacy_accepted_at: datetime | None
    privacy_policy_version: str | None
    terms_accepted_at: datetime | None
    terms_version: str | None
    created_at: datetime


class UserWithCompanyRead(BaseModel):
    """Schema for user with company profile."""

    user: UserRead
    company_profile: CompanyProfileRead


class CompanyDataExport(BaseModel):
    """Right-to-data-portability export payload for a company.

    File URLs on the embedded ``company_profile`` are presigned (1-hour
    validity for S3) so the recipient can download them without a
    follow-up auth round-trip.
    """

    exported_at: datetime
    user: UserRead
    company_profile: CompanyProfileRead
    jobs: list[JobRead]


class PendingCompanyRead(BaseModel):
    """Schema for pending company registration (user + company profile)."""

    user: UserRead
    company_profile: CompanyProfileRead
    invitation_sent: bool = False


class ApprovedCompanyRead(BaseModel):
    """Schema for approved company (user + company profile)."""

    user: UserRead
    company_profile: CompanyProfileRead


class ActiveCompanyRead(BaseModel):
    """Schema for an active company in the admin company list.

    ``user`` is ``None`` for profiles created directly by admins (user_id=null).
    """

    user: UserRead | None
    company_profile: CompanyProfileRead


class CompanyProfileAdminCreate(BaseModel):
    """Schema for an admin creating a company profile without a user account."""

    name: str = Field(..., max_length=100)
    company_id: str  # ח.פ — 9-digit Israeli company registration number
    address: str = Field(..., max_length=200)
    contact_email: EmailStr = Field(..., max_length=255)
    contact_first_name: str = Field(..., min_length=2, max_length=100)
    contact_last_name: str = Field(..., min_length=2, max_length=100)
    contact_mobile_phone: str
    contact_landline_phone: str | None = Field(None, max_length=20)

    @field_validator("company_id")
    @classmethod
    def validate_company_id(cls, v: str) -> str:
        if not re.fullmatch(r"\d{9}", v):
            raise ValueError("Company ID must be exactly 9 digits")
        return v

    @field_validator("contact_mobile_phone")
    @classmethod
    def validate_mobile_phone(cls, v: str) -> str:
        if not re.fullmatch(r"05[0-9]\d{7}", v):
            raise ValueError(
                "Mobile phone must be a valid Israeli mobile number (05X-XXXXXXX)"
            )
        return v


class CompanyProfileSelfUpdate(BaseModel):
    """Partial-update schema for a company editing its own profile.

    Excludes ``company_id`` (immutable ח.פ), ``contact_email`` (login identity),
    and logo (requires a separate upload flow).
    """

    name: str | None = Field(None, max_length=100)
    address: str | None = Field(None, max_length=200)
    contact_first_name: str | None = Field(None, min_length=2, max_length=100)
    contact_last_name: str | None = Field(None, min_length=2, max_length=100)
    contact_mobile_phone: str | None = None
    contact_landline_phone: str | None = Field(None, max_length=20)

    @field_validator("name", "address", "contact_first_name", "contact_last_name")
    @classmethod
    def reject_explicit_null(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("Field cannot be set to null on update")
        return v

    @field_validator("contact_mobile_phone")
    @classmethod
    def validate_mobile_phone(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("contact_mobile_phone cannot be set to null on update")
        if not re.fullmatch(r"05[0-9]\d{7}", v):
            raise ValueError(
                "Mobile phone must be a valid Israeli mobile number (05X-XXXXXXX)"
            )
        return v


class CompanyStats(BaseModel):
    """Aggregated stats for a company's own dashboard."""

    active_jobs: int
    pending_jobs: int
    closed_jobs: int
    total_applications: int
    applications_by_status: dict[str, int]


class CompanyApplicationCandidateRead(BaseModel):
    """Minimal candidate snapshot embedded in company-facing application rows."""

    id: int
    full_name: str
    email: str
    phone: str | None


class CompanyApplicationRead(BaseModel):
    """Company-facing view of an application for a job they own."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    candidate_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    match_score: float | None = None
    ai_review: str | None = None
    candidate: CompanyApplicationCandidateRead


class CompanyApplicationStatusUpdate(BaseModel):
    """Payload for a company updating an application's status."""

    status: str


class CompanyJobRecommendationRead(BaseModel):
    """AI-ranked candidate suggestion for a company's job."""

    candidate_id: int
    full_name: str
    email: str
    phone: str | None
    score: float


class CompanyProfileAdminUpdate(BaseModel):
    """Partial-update schema for an admin editing a company profile.

    The five fields ``name``, ``company_id``, ``address``, ``contact_first_name``,
    ``contact_last_name``, and ``contact_mobile_phone`` are NOT NULL in the
    database. They stay typed as Optional only for partial-update semantics
    (omit-to-leave-unchanged); an explicit ``null`` is rejected by validators
    so a PATCH cannot bypass the DB constraint.
    """

    name: str | None = Field(None, max_length=100)
    company_id: str | None = None
    address: str | None = Field(None, max_length=200)
    contact_email: EmailStr | None = Field(None, max_length=255)
    contact_first_name: str | None = Field(None, min_length=2, max_length=100)
    contact_last_name: str | None = Field(None, min_length=2, max_length=100)
    contact_mobile_phone: str | None = None
    contact_landline_phone: str | None = Field(None, max_length=20)

    @field_validator(
        "name",
        "address",
        "contact_email",
        "contact_first_name",
        "contact_last_name",
    )
    @classmethod
    def reject_explicit_null(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("Field cannot be set to null on update")
        return v

    @field_validator("company_id")
    @classmethod
    def validate_company_id(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("company_id cannot be set to null on update")
        if not re.fullmatch(r"\d{9}", v):
            raise ValueError("Company ID must be exactly 9 digits")
        return v

    @field_validator("contact_mobile_phone")
    @classmethod
    def validate_mobile_phone(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("contact_mobile_phone cannot be set to null on update")
        if not re.fullmatch(r"05[0-9]\d{7}", v):
            raise ValueError(
                "Mobile phone must be a valid Israeli mobile number (05X-XXXXXXX)"
            )
        return v
