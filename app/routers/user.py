from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models import User, UserCreate, UserResponse

router = APIRouter(prefix="/api/user", tags=["user"])


@router.post("/register", response_model=UserResponse)
def register_user(data: UserCreate, session: Session = Depends(get_session)):
    """Register a new user or return existing user by display_name."""
    name = data.display_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    if len(name) > 50:
        raise HTTPException(status_code=400, detail="Name too long (max 50 chars)")

    # Check if user already exists
    existing = session.exec(
        select(User).where(User.display_name == name)
    ).first()
    if existing:
        return UserResponse(id=existing.id, display_name=existing.display_name)

    user = User(display_name=name)
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserResponse(id=user.id, display_name=user.display_name)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: str, session: Session = Depends(get_session)):
    """Get user by ID."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(id=user.id, display_name=user.display_name)
