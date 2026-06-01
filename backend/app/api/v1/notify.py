from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import ok
from app.deps import get_current_user, get_db
from app.models.user import User
from app.services import notify_service

router = APIRouter(prefix="/notify", tags=["notify"])


class SubscribeReportRequest(BaseModel):
    results: dict[str, str]   # {"booking_success": "accept"|"reject"|"ban", ...}


@router.post("/subscribe-report", summary="上报订阅消息结果")
def subscribe_report(
    req: SubscribeReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    quota = notify_service.report_subscribe(db, current_user.id, req.results)
    return ok({"quota": quota})


@router.get("/quota", summary="查询当前用户订阅配额")
def get_quota(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    quota = notify_service.get_quota(db, current_user.id)
    return ok({"quota": quota})
