"""Explicit request validation shared by the API routes."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

TOPICS = ("algebra", "geometry", "python", "robotics", "writing", "presentations", "science", "physics", "study_skills", "school_transition")
SLOTS = ("Mon 16:00", "Tue 16:00", "Wed 16:00", "Thu 16:00", "Fri 16:00", "Sat 10:00")
PREFERENCES = ("step_by_step", "practice", "encouragement")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProfileInput(StrictModel):
    alias: str = Field(min_length=2, max_length=28, pattern=r"^[A-Za-z][A-Za-z0-9 _-]*$")
    avatar_id: Literal["bolt", "orbit", "comet", "shield"]
    grade_band: Literal["middle", "high"]
    strengths: list[str] = Field(default_factory=list, max_length=10)
    needs: list[str] = Field(default_factory=list, max_length=10)
    available_slots: list[str] = Field(default_factory=list, max_length=6)
    capacity: int = Field(default=2, ge=0, le=5, strict=True)
    support_preferences: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("strengths", "needs", "available_slots", "support_preferences")
    @classmethod
    def allowed_values(cls, values, info):
        allowed = SLOTS if info.field_name == "available_slots" else PREFERENCES if info.field_name == "support_preferences" else TOPICS
        if any(value not in allowed for value in values):
            raise ValueError(f"Choose values from: {', '.join(allowed)}")
        if len(values) != len(set(values)):
            raise ValueError("Duplicate selections are not allowed")
        return values


class MissionInput(StrictModel):
    requester_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=8, max_length=1500)


class MissionUpdate(StrictModel):
    status: Literal["open", "completed", "cancelled"]


class MatchInput(StrictModel):
    mission_id: str = Field(min_length=1, max_length=100)
    mentor_id: str = Field(min_length=1, max_length=100)


class ReportInput(StrictModel):
    reporter_id: str = Field(min_length=1, max_length=100)
    target_type: Literal["mission", "profile", "match"]
    target_id: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=5, max_length=500)


class BlockInput(StrictModel):
    blocker_id: str = Field(min_length=1, max_length=100)
    blocked_id: str = Field(min_length=1, max_length=100)


class BatchInput(StrictModel):
    dry_run: bool = Field(default=True, strict=True)


class ResetInput(StrictModel):
    confirm: Literal[True]

    @field_validator("confirm", mode="before")
    @classmethod
    def explicit_true(cls, value):
        if value is not True:
            raise ValueError("Reset requires the JSON boolean confirm: true")
        return value
