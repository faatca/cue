import secrets
from starlette.middleware.base import BaseHTTPMiddleware


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        csrf = request.session.get("csrf")
        if not csrf:
            csrf = secrets.token_urlsafe()
            request.session["csrf"] = csrf
        request.state.csrf = csrf
        response = await call_next(request)
        return response
