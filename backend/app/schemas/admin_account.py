"""مخططاتُ حساب المشرف نفسِه."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AdminAccountOut(BaseModel):
    username: str | None
    is_break_glass: bool
    # يقرؤه الشاشةُ فتقول «لا استعادة ذاتية» لمن لا رقمَ له (SPEC §25.9)
    has_phone: bool


class ChangeUsernameIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    # الحدّان للنقل، والسياسةُ في `validate_password` — لا تُكرَّر هنا
    new_password: str = Field(min_length=8, max_length=128)
