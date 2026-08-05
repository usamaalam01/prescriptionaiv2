from pydantic import BaseModel, Field, field_validator


class PharmacistRegistrationIn(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=12, max_length=200)
    confirm_password: str = Field(min_length=12, max_length=200)
    pharmacist_registration_id: str = Field(min_length=1, max_length=100)
    age_over_18: bool
    pis_version: str
    pis_scroll_acknowledged: bool
    pis_label_accepted: bool
    consent_form_version: str
    accepted_statement_numbers: list[int] = Field(min_length=18, max_length=18)
    electronic_affirmation: bool

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, value: str, info):
        if info.data.get("password") and value != info.data["password"]:
            raise ValueError("Passwords do not match")
        return value


class RegistrationOut(BaseModel):
    id: str
    user_id: str
    status: str
    message: str = "Registration submitted and awaiting administrator approval."

    model_config = {"from_attributes": True}


class DecisionIn(BaseModel):
    confirmed_role: str = "pharmacist"
    reason: str | None = None


class RegistrationListItem(BaseModel):
    id: str
    user_id: str
    username: str
    requested_role: str
    status: str
    submitted_at: str | None
    encrypted_registration_data: bool = True
