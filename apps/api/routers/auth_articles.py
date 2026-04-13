from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlite3 import IntegrityError

from ..schemas.auth_articles import (
    ArticleCreateRequest,
    ArticleResponse,
    ArticleUpdateRequest,
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    ViewerResponse,
)
from ..services.auth_articles_db import (
    authenticate_user,
    create_article,
    create_token,
    create_user,
    get_article,
    list_articles,
    parse_token,
    update_article,
)

router = APIRouter(prefix="/api", tags=["auth", "articles"])


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    payload = parse_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return {
        "id": payload["sub"],
        "email": payload["email"],
        "display_name": payload["display_name"],
        "role": payload["role"],
    }


@router.post("/auth/register", response_model=AuthResponse, status_code=201)
def register(payload: RegisterRequest) -> AuthResponse:
    try:
        user = create_user(payload.email, payload.password, payload.display_name)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Email already exists") from exc
    token = create_token(user)
    return AuthResponse(access_token=token, user_id=user["id"], email=user["email"], display_name=user["display_name"], role=user["role"])


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    user = authenticate_user(payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(user)
    return AuthResponse(access_token=token, user_id=user["id"], email=user["email"], display_name=user["display_name"], role=user["role"])


@router.get("/auth/me", response_model=ViewerResponse)
def me(user: dict = Depends(get_current_user)) -> ViewerResponse:
    return ViewerResponse(user_id=user["id"], email=user["email"], display_name=user["display_name"], role=user["role"])


@router.get("/articles", response_model=list[ArticleResponse])
def get_articles(user: dict = Depends(get_current_user)) -> list[ArticleResponse]:
    return [ArticleResponse.model_validate(row) for row in list_articles(user["role"], user["id"])]


@router.post("/articles", response_model=ArticleResponse, status_code=201)
def post_article(payload: ArticleCreateRequest, user: dict = Depends(get_current_user)) -> ArticleResponse:
    article = create_article(author_id=user["id"], title=payload.title, summary=payload.summary, content=payload.content)
    return ArticleResponse.model_validate(article)


@router.patch("/articles/{article_id}", response_model=ArticleResponse)
def patch_article(article_id: str, payload: ArticleUpdateRequest, user: dict = Depends(get_current_user)) -> ArticleResponse:
    existing = get_article(article_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Article not found")

    if user["role"] not in {"moderator", "admin"}:
        raise HTTPException(status_code=403, detail="Only moderator/admin can edit articles")

    updated = update_article(article_id, payload.model_dump(exclude_none=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return ArticleResponse.model_validate(updated)
