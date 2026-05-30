from fastapi import APIRouter

from app.api.v1 import admin, admin_logs, auth, audios, dm, me, orders

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(audios.router)
api_router.include_router(me.router)
api_router.include_router(admin.router)
api_router.include_router(admin_logs.router)
api_router.include_router(orders.router)
api_router.include_router(dm.admin_router)
api_router.include_router(dm.me_router)
