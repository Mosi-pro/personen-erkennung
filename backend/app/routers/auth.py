from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import config, db, security

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class ChangePw(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(min_length=10, max_length=256)


def _set_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(security.COOKIE, token, max_age=config.SESSION_HOURS * 3600, httponly=True, samesite="strict",
                    secure=config.COOKIE_SECURE, path="/")


@router.post("/login")
def login(body: Login, request: Request, response: Response):
    ip = request.client.host if request.client else "?"
    security.rate_limit(f"login:{ip}", 10, 60)
    if security.login_locked(body.username):
        raise HTTPException(429, "Konto vorübergehend gesperrt (zu viele Fehlversuche). Bitte in 15 Minuten erneut versuchen.")
    u = db.one("SELECT * FROM users WHERE username=?", (body.username,))
    ok = security.verify_password(body.password, u["password_hash"]) if u else security.verify_password(body.password, security.hash_password("x"))
    if not u or not ok:
        security.login_failed(body.username)
        raise HTTPException(401, "Benutzername oder Passwort falsch.")
    security.login_ok(body.username)
    token, csrf = security.create_session(u["id"])
    _set_cookie(response, token)
    return {"username": u["username"], "csrf": csrf}


@router.post("/logout")
def logout(request: Request, response: Response, user=Depends(security.auth)):
    token = request.cookies.get(security.COOKIE)
    if token:
        security.destroy_session(token)
    response.delete_cookie(security.COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user=Depends(security.auth)):
    return {"username": user["username"], "csrf": user["csrf"]}


@router.post("/password")
def change_password(body: ChangePw, response: Response, user=Depends(security.auth)):
    u = db.one("SELECT * FROM users WHERE id=?", (user["id"],))
    if not security.verify_password(body.current_password, u["password_hash"]):
        raise HTTPException(400, "Aktuelles Passwort ist falsch.")
    db.run("UPDATE users SET password_hash=? WHERE id=?", (security.hash_password(body.new_password), user["id"]))
    security.destroy_user_sessions(user["id"])
    response.delete_cookie(security.COOKIE, path="/")
    return {"ok": True, "message": "Passwort geändert. Bitte neu anmelden."}
