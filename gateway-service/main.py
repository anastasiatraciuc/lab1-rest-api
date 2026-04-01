"""
Gateway Service — точка входа, проксирует запросы к Users Service.
Паттерны: Gateway / API Proxy, Circuit Breaker (базовая обработка ошибок)
Межсервисная коммуникация: httpx (async HTTP-клиент)
"""
import os
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

# ─────────────────────────────────────────────
# Конфигурация (через переменные окружения)
# ─────────────────────────────────────────────

USERS_SERVICE_URL: str = os.getenv("USERS_SERVICE_URL", "http://localhost:8001")
REQUEST_TIMEOUT: float = float(os.getenv("REQUEST_TIMEOUT", "5.0"))


# ─────────────────────────────────────────────
# DTO (зеркало контракта Users Service)
# ─────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, example="Bob Jones")
    email: str = Field(..., example="bob@example.com")

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None


# ─────────────────────────────────────────────
# HTTP-клиент (общий для всего приложения)
# ─────────────────────────────────────────────

def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=USERS_SERVICE_URL, timeout=REQUEST_TIMEOUT)


def _raise_if_error(response: httpx.Response) -> None:
    """Прокидывает HTTP-ошибки вышестоящему клиенту."""
    if response.status_code == 404:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=response.json().get("detail", "Not found"))
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code,
                            detail=response.text)


# ─────────────────────────────────────────────
# Application
# ─────────────────────────────────────────────

app = FastAPI(
    title="Gateway Service",
    description="API-шлюз — агрегирует запросы и делегирует в Users Service",
    version="1.0.0",
)


# Health check (также проверяет доступность Users Service)
@app.get("/health", tags=["system"])
async def health_check():
    upstream_ok = False
    try:
        async with _client() as client:
            r = await client.get("/health")
            upstream_ok = r.status_code == 200
    except Exception:
        pass
    return {
        "status": "ok",
        "service": "gateway-service",
        "version": "1.0.0",
        "upstream": {
            "users-service": "ok" if upstream_ok else "unavailable",
            "url": USERS_SERVICE_URL,
        },
    }


# ── Proxy endpoints ───────────────────────────────────────────────────────────

@app.get("/api/users", tags=["users"])
async def list_users():
    async with _client() as client:
        r = await client.get("/users")
        _raise_if_error(r)
        return r.json()


@app.get("/api/users/{user_id}", tags=["users"])
async def get_user(user_id: str):
    async with _client() as client:
        r = await client.get(f"/users/{user_id}")
        _raise_if_error(r)
        return r.json()


@app.post("/api/users", status_code=status.HTTP_201_CREATED, tags=["users"])
async def create_user(payload: UserCreate):
    async with _client() as client:
        r = await client.post("/users", json=payload.dict())
        _raise_if_error(r)
        return r.json()


@app.put("/api/users/{user_id}", tags=["users"])
async def update_user(user_id: str, payload: UserUpdate):
    async with _client() as client:
        r = await client.put(f"/users/{user_id}", json=payload.dict(exclude_none=True))
        _raise_if_error(r)
        return r.json()


@app.delete("/api/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["users"])
async def delete_user(user_id: str):
    async with _client() as client:
        r = await client.delete(f"/users/{user_id}")
        _raise_if_error(r)