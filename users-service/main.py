"""
Users Service — управление пользователями.
Паттерны: Repository, DTO (Pydantic), Layered Architecture
"""
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

# ─────────────────────────────────────────────
# DTO  (Data Transfer Objects)
# ─────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, example="Alice Smith")
    email: str = Field(..., example="alice@example.com")

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=64)
    email: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    name: str
    email: str

# ─────────────────────────────────────────────
# Repository  (абстракция доступа к данным)
# ─────────────────────────────────────────────

class UserRepository:
    """In-memory хранилище пользователей."""

    def __init__(self) -> None:
        self._db: dict[str, UserResponse] = {}

    def create(self, payload: UserCreate) -> UserResponse:
        user = UserResponse(id=str(uuid.uuid4()), **payload.dict())
        self._db[user.id] = user
        return user

    def get_all(self) -> list[UserResponse]:
        return list(self._db.values())

    def get_by_id(self, user_id: str) -> Optional[UserResponse]:
        return self._db.get(user_id)

    def update(self, user_id: str, payload: UserUpdate) -> Optional[UserResponse]:
        user = self._db.get(user_id)
        if user is None:
            return None
        updated = user.copy(update=payload.dict(exclude_none=True))
        self._db[user_id] = updated
        return updated

    def delete(self, user_id: str) -> bool:
        if user_id not in self._db:
            return False
        del self._db[user_id]
        return True


# ─────────────────────────────────────────────
# Application
# ─────────────────────────────────────────────

app = FastAPI(
    title="Users Service",
    description="Микросервис управления пользователями",
    version="1.0.0",
)

_repo = UserRepository()


# Health check
@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok", "service": "users-service", "version": "1.0.0"}


# CRUD endpoints
@app.get("/users", response_model=list[UserResponse], tags=["users"])
def list_users():
    """Получить список всех пользователей."""
    return _repo.get_all()


@app.get("/users/{user_id}", response_model=UserResponse, tags=["users"])
def get_user(user_id: str):
    """Получить пользователя по ID."""
    user = _repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@app.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["users"])
def create_user(payload: UserCreate):
    """Создать нового пользователя."""
    return _repo.create(payload)


@app.put("/users/{user_id}", response_model=UserResponse, tags=["users"])
def update_user(user_id: str, payload: UserUpdate):
    """Обновить данные пользователя."""
    user = _repo.update(user_id, payload)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["users"])
def delete_user(user_id: str):
    """Удалить пользователя."""
    if not _repo.delete(user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")