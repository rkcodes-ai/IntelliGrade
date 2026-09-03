"""
Regression tests for `app.core.exceptions`.

Pydantic's `RequestValidationError.errors()` can include a raw exception
object in the `ctx` field when a custom validator raises `ValueError` —
passing that straight to `JSONResponse` (which uses stdlib `json.dumps`)
crashes instead of returning a clean 422. These tests build a throwaway app
(not the real router) so the failure mode can be reproduced without adding
a test-only endpoint to the actual application.
"""

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, field_validator

from app.core.exceptions import register_exception_handlers


def _build_test_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    class Payload(BaseModel):
        name: str

        @field_validator("name")
        @classmethod
        def _reject_blank(cls, value: str) -> str:
            if not value.strip():
                # Pydantic wraps this in `ctx={"error": ValueError(...)}`,
                # which is not directly JSON-serializable.
                raise ValueError("name must not be blank")
            return value

    @app.post("/items")
    async def create_item(payload: Payload) -> dict[str, str]:
        return {"name": payload.name}

    return app


async def test_validation_error_with_custom_validator_returns_clean_422() -> None:
    app = _build_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/items", json={"name": "   "})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "errors" in body["error"]["details"]


async def test_valid_payload_still_succeeds() -> None:
    app = _build_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/items", json={"name": "Answer Script"})

    assert response.status_code == 200
    assert response.json() == {"name": "Answer Script"}
