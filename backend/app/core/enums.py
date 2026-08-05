from enum import StrEnum


class UserRole(StrEnum):
    ADMINISTRATOR = "administrator"
    PHARMACIST = "pharmacist"
    REVIEWER = "reviewer"


class UserStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"
    PASSWORD_RESET_REQUIRED = "password_reset_required"


class RegistrationStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
