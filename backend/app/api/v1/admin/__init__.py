from datetime import date as DateType

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.response import ok
from app.core.timezone import utc_to_shanghai
from app.deps import get_current_admin, get_db
from app.models.admin_user import AdminUser
from app.schemas.admin import (
    AdminCancelRequest,
    ChangePasswordRequest,
    ConfigUpdateRequest,
    DeptCreateRequest,
    DeptOut,
    DeptUpdateRequest,
    GrantDeptsRequest,
    GrantUsersRequest,
    RoomCreateRequest,
    RoomOut,
    RoomPermissionsOut,
    RoomUpdateRequest,
    UserOut,
    UserUpdateRequest,
)
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


def _serialize_booking(b) -> dict:
    return {
        "id": b.id,
        "room_id": b.room_id,
        "user_id": b.user_id,
        "date": str(b.date),
        "start_at": utc_to_shanghai(b.start_at).isoformat(),
        "end_at": utc_to_shanghai(b.end_at).isoformat(),
        "preset": b.preset,
        "title": b.title,
        "status": b.status,
        "cancel_reason": b.cancel_reason,
        "recurrence_id": b.recurrence_id,
    }


# ── Rooms ─────────────────────────────────────────────────────────────────────

@router.get("/rooms", summary="会议室列表（管理端）")
def admin_list_rooms(
    keyword: str | None = Query(None),
    status: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    items, total = admin_service.list_rooms(db, keyword, status, page, page_size)
    return ok({"list": [RoomOut.model_validate(r).model_dump() for r in items],
                "total": total, "page": page})


@router.post("/rooms", summary="创建会议室")
def admin_create_room(
    req: RoomCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    room = admin_service.create_room(db, req)
    return ok(RoomOut.model_validate(room).model_dump())


@router.put("/rooms/{room_id}", summary="更新会议室")
def admin_update_room(
    room_id: int,
    req: RoomUpdateRequest,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    room = admin_service.update_room(db, room_id, req)
    return ok(RoomOut.model_validate(room).model_dump())


@router.delete("/rooms/{room_id}", summary="停用会议室（软删）")
def admin_delete_room(
    room_id: int,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    admin_service.delete_room(db, room_id)
    return ok({"room_id": room_id})


# ── Permissions ───────────────────────────────────────────────────────────────

@router.get("/rooms/{room_id}/permissions", summary="查看会议室授权")
def admin_get_permissions(
    room_id: int,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    data = admin_service.get_room_permissions(db, room_id)
    out = RoomPermissionsOut(
        users=[UserOut.model_validate(u).model_dump() for u in data["users"]],
        depts=[DeptOut.model_validate(d).model_dump() for d in data["depts"]],
    )
    return ok(out.model_dump())


@router.post("/rooms/{room_id}/permissions/users", summary="批量授权用户")
def admin_grant_users(
    room_id: int,
    req: GrantUsersRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    admin_service.grant_users(db, room_id, req.user_ids, admin.id)
    return ok({"room_id": room_id, "granted_users": req.user_ids})


@router.delete("/rooms/{room_id}/permissions/users/{user_id}", summary="撤销用户授权")
def admin_revoke_user(
    room_id: int,
    user_id: int,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    admin_service.revoke_user(db, room_id, user_id)
    return ok({"room_id": room_id, "user_id": user_id})


@router.post("/rooms/{room_id}/permissions/depts", summary="批量授权部门")
def admin_grant_depts(
    room_id: int,
    req: GrantDeptsRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    admin_service.grant_depts(db, room_id, req.dept_ids, admin.id)
    return ok({"room_id": room_id, "granted_depts": req.dept_ids})


@router.delete("/rooms/{room_id}/permissions/depts/{dept_id}", summary="撤销部门授权")
def admin_revoke_dept(
    room_id: int,
    dept_id: int,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    admin_service.revoke_dept(db, room_id, dept_id)
    return ok({"room_id": room_id, "dept_id": dept_id})


@router.get("/users/{user_id}/rooms", summary="某用户可见会议室")
def admin_get_user_rooms(
    user_id: int,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    rooms = admin_service.get_user_rooms(db, user_id)
    return ok([RoomOut.model_validate(r).model_dump() for r in rooms])


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users", summary="用户列表")
def admin_list_users(
    keyword: str | None = Query(None),
    dept_id: int | None = Query(None),
    status: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    items, total = admin_service.list_users(db, keyword, dept_id, status, page, page_size)
    return ok({"list": [UserOut.model_validate(u).model_dump() for u in items],
                "total": total, "page": page})


@router.put("/users/{user_id}", summary="修改用户信息")
def admin_update_user(
    user_id: int,
    req: UserUpdateRequest,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    user = admin_service.update_user(db, user_id, req)
    return ok(UserOut.model_validate(user).model_dump())


# ── Departments ───────────────────────────────────────────────────────────────

@router.get("/departments", summary="部门列表")
def admin_list_departments(
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    depts = admin_service.list_departments(db)
    return ok([DeptOut.model_validate(d).model_dump() for d in depts])


@router.post("/departments", summary="创建部门")
def admin_create_department(
    req: DeptCreateRequest,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    dept = admin_service.create_department(db, req)
    return ok(DeptOut.model_validate(dept).model_dump())


@router.put("/departments/{dept_id}", summary="修改部门")
def admin_update_department(
    dept_id: int,
    req: DeptUpdateRequest,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    dept = admin_service.update_department(db, dept_id, req)
    return ok(DeptOut.model_validate(dept).model_dump())


@router.delete("/departments/{dept_id}", summary="删除部门")
def admin_delete_department(
    dept_id: int,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    admin_service.delete_department(db, dept_id)
    return ok({"dept_id": dept_id})


# ── Bookings ──────────────────────────────────────────────────────────────────

@router.get("/bookings", summary="预订总览")
def admin_list_bookings(
    room_id: int | None = Query(None),
    user_id: int | None = Query(None),
    date_from: DateType | None = Query(None),
    date_to: DateType | None = Query(None),
    status: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    items, total = admin_service.list_bookings(
        db, room_id, user_id, date_from, date_to, status, page, page_size
    )
    return ok({"list": [_serialize_booking(b) for b in items], "total": total, "page": page})


@router.post("/bookings/{booking_id}/cancel", summary="管理员强制取消预订")
def admin_cancel_booking(
    booking_id: int,
    req: AdminCancelRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    b = admin_service.admin_cancel_booking(db, booking_id, admin.id, req.reason)
    return ok(_serialize_booking(b))


@router.get("/stats/overview", summary="数据概览")
def admin_stats_overview(
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    return ok(admin_service.stats_overview(db))


# ── Config ────────────────────────────────────────────────────────────────────

@router.get("/config", summary="查看系统参数")
def admin_get_config(
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    return ok(admin_service.get_config(db))


@router.put("/config", summary="更新系统参数")
def admin_update_config(
    req: ConfigUpdateRequest,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    return ok(admin_service.update_config(db, req))


# ── Admin self ────────────────────────────────────────────────────────────────

@router.put("/me/password", summary="管理员修改密码")
def admin_change_password(
    req: ChangePasswordRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    admin_service.change_admin_password(db, admin.id, req.old_password, req.new_password)
    return ok({"message": "密码修改成功"})
