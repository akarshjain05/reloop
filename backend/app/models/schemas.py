from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
Condition = Literal["like_new", "good", "fair", "damaged"]
Action = Literal["resell", "repair", "recycle", "donate"]


class LoginIn(BaseModel):
    email: str = Field(pattern=EMAIL_RE, max_length=120)
    password: str = Field(min_length=1, max_length=128)


class RegisterIn(BaseModel):
    email: str = Field(pattern=EMAIL_RE, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=60)
    building_id: str | None = Field(default=None, max_length=60)


class Corrections(BaseModel):
    item_type: str | None = Field(default=None, max_length=40)
    brand: str | None = Field(default=None, max_length=40)
    condition: Condition | None = None
    quantity: int | None = Field(default=None, ge=1, le=50)
    weight_kg: float | None = Field(default=None, gt=0, le=100, description="Approximate weight of ONE item in kg")


class ConfirmIn(BaseModel):
    submission_id: str = Field(max_length=60)
    corrections: Corrections | None = None


class ActionIn(BaseModel):
    action: Action


class AddressIn(BaseModel):
    line: str = Field(min_length=5, max_length=200)
    city: str = Field(min_length=2, max_length=60)
    pincode: str | None = Field(default=None, pattern=r"^\d{6}$")


class PickupIn(BaseModel):
    submission_ids: list[str] = Field(min_length=1, max_length=20)
    mode: Literal["pickup", "dropoff"] = "pickup"
    recycler_id: str | None = Field(default=None, max_length=60)
    address: AddressIn | None = None
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    slot: str | None = Field(default=None, max_length=20)


class StatusIn(BaseModel):
    status: Literal["scheduled", "collector_assigned", "picked_up", "verified", "recycled", "cancelled"]
    verified_weight_kg: float | None = Field(default=None, gt=0, le=500)
    verified_match: bool = True
    note: str | None = Field(default=None, max_length=200)
    collector_id: str | None = Field(default=None, max_length=60)


class VerifyIn(BaseModel):
    pickup_id: str = Field(max_length=60)
    verified_weight_kg: float | None = Field(default=None, gt=0, le=500)
    verified_match: bool = True


class AdvisorIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    history: list[dict] = Field(default_factory=list, max_length=12)


class ResolveIn(BaseModel):
    action: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=200)


class AdjustIn(BaseModel):
    user_id: str = Field(max_length=60)
    points: int = Field(ge=-1000, le=1000)
    reason: str = Field(min_length=3, max_length=120)


class ChallengeIn(BaseModel):
    title: str = Field(min_length=3, max_length=80)
    description: str = Field(default="", max_length=300)
    metric: Literal["kg", "items"] = "items"
    goal: float = Field(gt=0, le=1_000_000)
    reward_points: int = Field(default=500, ge=0, le=50_000)
    days: int = Field(default=14, ge=1, le=120)
    item_type: str | None = Field(default=None, max_length=40)
    category: str | None = Field(default=None, max_length=40)
    scope: Literal["global", "org"] = "org"


class RecyclerIn(BaseModel):
    name: str | None = Field(default=None, max_length=90)
    address: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=60)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    accepts: list[str] | None = None
    hours: str | None = Field(default=None, max_length=80)
    pickup_available: bool | None = None
    min_pickup_kg: float | None = Field(default=None, ge=0, le=1000)
    processing_days: int | None = Field(default=None, ge=0, le=90)
    rating: float | None = Field(default=None, ge=0, le=5)
    verification_status: Literal["verified", "verified_demo", "unverified"] | None = None
    license_no: str | None = Field(default=None, max_length=60)
    valid_until: str | None = Field(default=None, max_length=20)
