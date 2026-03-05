from fastapi import APIRouter, Header, HTTPException

from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/verify")
async def verify_token(x_admin_token: str = Header(...)):
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return {"status": "ok"}
