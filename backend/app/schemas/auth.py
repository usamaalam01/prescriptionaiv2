from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)


class ForgotPasswordRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)


class ForgotPasswordResponse(BaseModel):
    """Academic prototype: no email — temporary password returned when the account exists."""

    message: str
    temporary_password: str | None = None


class UserOut(BaseModel):
    id: str
    username: str
    role: str
    status: str
    must_change_password: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
