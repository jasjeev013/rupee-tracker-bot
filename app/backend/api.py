import hmac
from dataclasses import asdict
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.backend import service
from app.backend.db import connect
from app.backend.ratelimit import RateLimiter
from app.bot.parser import MAX_AMOUNT_PAISE, MAX_TEXT_LEN
from app.config import Settings


class ExpenseIn(BaseModel):
    user_id: int
    description: str = Field(min_length=1, max_length=MAX_TEXT_LEN)
    amount_paise: int = Field(gt=0, le=MAX_AMOUNT_PAISE)


class AssignIn(BaseModel):
    user_id: int
    category_id: int


class CategoryIn(BaseModel):
    user_id: int
    name: str = Field(min_length=1, max_length=service.MAX_NAME_LEN * 2)


class FeedbackIn(BaseModel):
    user_id: int
    message: str = Field(min_length=1, max_length=service.MAX_FEEDBACK_LEN)


def create_app(settings: Settings, rate_limit: tuple[int, float] = (30, 60)) -> FastAPI:
    app = FastAPI(title="Rupee Tracker Backend")
    limiter = RateLimiter(*rate_limit)

    def verify_secret(x_bot_secret: str = Header(default="")) -> None:
        if not hmac.compare_digest(x_bot_secret.encode(), settings.backend_secret.encode()):
            raise HTTPException(401, "bad secret")

    def get_conn():
        conn = connect(settings.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def guard(conn, user_id: int) -> None:
        if not limiter.allow(user_id):
            raise HTTPException(429, "rate limited")
        service.ensure_user(conn, user_id)

    auth = [Depends(verify_secret)]

    @app.post("/expenses", dependencies=auth)
    def add_expense(body: ExpenseIn, conn=Depends(get_conn)):
        guard(conn, body.user_id)
        try:
            r = service.add_expense(conn, body.user_id, body.description, body.amount_paise)
        except service.LimitExceeded as e:
            raise HTTPException(409, str(e))
        return asdict(r)

    @app.post("/expenses/{expense_id}/category", dependencies=auth)
    def assign(expense_id: int, body: AssignIn, conn=Depends(get_conn)):
        guard(conn, body.user_id)
        try:
            name = service.assign_category(conn, body.user_id, expense_id, body.category_id)
        except service.NotFound as e:
            raise HTTPException(404, str(e))
        return {"category": name}

    @app.get("/categories", dependencies=auth)
    def categories(user_id: int, conn=Depends(get_conn)):
        guard(conn, user_id)
        return [asdict(c) for c in service.list_categories(conn, user_id)]

    @app.post("/categories", dependencies=auth)
    def create_category(body: CategoryIn, conn=Depends(get_conn)):
        guard(conn, body.user_id)
        try:
            return asdict(service.create_category(conn, body.user_id, body.name))
        except ValueError as e:
            raise HTTPException(422, str(e))
        except service.LimitExceeded as e:
            raise HTTPException(409, str(e))

    @app.post("/feedback", dependencies=auth)
    def feedback(body: FeedbackIn, conn=Depends(get_conn)):
        guard(conn, body.user_id)
        try:
            service.add_feedback(conn, body.user_id, body.message)
        except ValueError as e:
            raise HTTPException(422, str(e))
        except service.LimitExceeded as e:
            raise HTTPException(409, str(e))
        return {"ok": True}

    @app.get("/today", dependencies=auth)
    def today(user_id: int, conn=Depends(get_conn)):
        guard(conn, user_id)
        return asdict(service.today(conn, user_id))

    @app.get("/stats", dependencies=auth)
    def stats(
        user_id: int,
        period: Literal["month", "last_month", "year"] = Query(...),
        conn=Depends(get_conn),
    ):
        guard(conn, user_id)
        return asdict(service.stats(conn, user_id, period))

    return app
