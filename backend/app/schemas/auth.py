"""Authentication flow request/response schemas."""

from pydantic import Field, field_validator

from app.core.password_policy import validate_password_field
from app.schemas.base import BaseSchema
from app.schemas.user import UserRead


class LoginRequest(BaseSchema):
    """`POST /auth/login` body. Accepts either username or email in `identifier`."""

    identifier: str = Field(min_length=1, max_length=320, description="Username or email address.")
    password: str = Field(min_length=1, max_length=72)
    remember_me: bool = False


class TokenResponse(BaseSchema):
    """Returned by `/auth/login` and `/auth/refresh`. The refresh token itself
    never appears in the body — it's set as an httpOnly cookie (see
    `docs/authentication-guide.md` for the CSRF/cookie posture)."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds.")
    user: UserRead | None = None


class ForgotPasswordRequest(BaseSchema):
    email: str = Field(min_length=3, max_length=320)


class ResetPasswordRequest(BaseSchema):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=72)

    _validate_new_password = field_validator("new_password")(validate_password_field)


class ChangePasswordRequest(BaseSchema):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)

    _validate_new_password = field_validator("new_password")(validate_password_field)


class MessageResponse(BaseSchema):
    """Generic acknowledgement body for endpoints with no meaningful return value."""

    message: str
