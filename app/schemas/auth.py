"""Auth-related request and response schemas."""

from pydantic import BaseModel, ConfigDict, Field


class SignUpRequest(BaseModel):
    """User registration payload."""

    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """User login payload."""

    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    """JWT access token response."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
