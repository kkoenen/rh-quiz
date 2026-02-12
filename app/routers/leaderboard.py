from fastapi import APIRouter, Depends, HTTPException, Header
from sqlmodel import Session, select
from typing import Optional
from app.database import get_session
from app.models import LeaderboardEntry, LeaderboardResponse
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("", response_model=LeaderboardResponse)
def get_leaderboard(session: Session = Depends(get_session)):
    """Get leaderboard sorted by total_score desc, tie-break by most recent update."""
    entries = session.exec(
        select(LeaderboardEntry)
        .order_by(LeaderboardEntry.total_score.desc(), LeaderboardEntry.last_updated.desc())
    ).all()

    last = entries[0].last_updated.isoformat() if entries else None

    return LeaderboardResponse(entries=list(entries), last_updated=last)


@router.delete("/reset")
def reset_leaderboard(
    x_admin_token: Optional[str] = Header(None),
    session: Session = Depends(get_session),
):
    """Reset the entire leaderboard. Requires admin token."""
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")

    entries = session.exec(select(LeaderboardEntry)).all()
    for entry in entries:
        session.delete(entry)
    session.commit()
    return {"message": "Leaderboard reset", "deleted": len(entries)}
