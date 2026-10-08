from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..core.errors import bad_request, forbidden
from ..services import challenges as chl
from ..services.leaderboard import leaderboard
from ..services.orgscore import org_summary
from .deps import current_user, get_c

router = APIRouter(tags=["community"])


@router.get("/leaderboard")
def lb_global(period: str = Query(default="month", pattern="^(month|all)$"), user=Depends(current_user), c=Depends(get_c)):
    return leaderboard(c, user, "global", period)


@router.get("/leaderboard/building")
def lb_building(period: str = Query(default="month", pattern="^(month|all)$"), user=Depends(current_user), c=Depends(get_c)):
    return leaderboard(c, user, "building", period)


@router.get("/leaderboard/campus")
def lb_campus(period: str = Query(default="month", pattern="^(month|all)$"), user=Depends(current_user), c=Depends(get_c)):
    return leaderboard(c, user, "campus", period)


@router.get("/leaderboard/neighborhood")
def lb_hood(period: str = Query(default="month", pattern="^(month|all)$"), user=Depends(current_user), c=Depends(get_c)):
    return leaderboard(c, user, "neighborhood", period)


@router.get("/challenges")
def challenges(user=Depends(current_user), c=Depends(get_c)):
    return chl.list_challenges(c, user)


@router.post("/challenges/{cid}/join")
def join(cid: str, user=Depends(current_user), c=Depends(get_c)):
    return chl.join(c, user, cid)


@router.get("/org/summary")
def summary(scope: str | None = Query(default=None, pattern="^(building|org)$"), scope_id: str | None = Query(default=None, max_length=60),
            user=Depends(current_user), c=Depends(get_c)):
    scope = scope or ("org" if user["role"] in ("ORGANIZATION_ADMIN", "ADMIN") else "building")
    if scope_id and user["role"] != "ADMIN" and scope_id not in (user.get("building_id"), user.get("org_id")):
        raise forbidden("You can only view your own building or organisation.")
    sid = scope_id or (user.get("org_id") if scope == "org" else user.get("building_id"))
    if not sid:
        raise bad_request("Join a building to see its dashboard.", "no_building")
    if scope == "org" and user["role"] == "USER" and not scope_id:
        scope, sid = "building", user.get("building_id")
    return org_summary(c, scope, sid)
