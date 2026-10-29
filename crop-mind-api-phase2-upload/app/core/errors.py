from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    codes = {400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT", 429: "RATE_LIMITED"}
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return JSONResponse(status_code=exc.status_code, content={"detail": detail, "code": codes.get(exc.status_code, "HTTP_ERROR"), "request_id": getattr(request.state, "request_id", None)}, headers=exc.headers)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "Invalid value"), "type": e.get("type", "value_error")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "Request validation failed.", "code": "VALIDATION_ERROR", "errors": errors, "request_id": getattr(request.state, "request_id", None)})
