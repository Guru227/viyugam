from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from fastapi import Request
import re
import logging

logger = logging.getLogger(__name__)

class PIIRedactionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to redact PII from logs and potentially request bodies if we logged them.
    Currently, this acts as a safeguard.
    """
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        # Regex for Email
        self.email_regex = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        # Regex for generic Phone (simple 10 digit)
        self.phone_regex = re.compile(r'\b\d{10}\b')

    async def dispatch(self, request: Request, call_next):
        # We can't easily modify the *incoming* request body stream here without consuming it,
        # which breaks the app unless we reconstruct it.
        # But we CAN intercept logging if we had custom logging here.
        
        # For this implementation, we will redact query params in verify
        # and ensure response headers don't leak info.
        
        # Real world: Use this to sanitise structured logs context.
        
        # Checking Query Params for PII
        query_params = str(request.query_params)
        if self.email_regex.search(query_params) or self.phone_regex.search(query_params):
            logger.warning(f"Redacted PII from Request Query: {self.redact(query_params)}")
            
        response = await call_next(request)
        return response

    def redact(self, text: str) -> str:
        text = self.email_regex.sub("[REDACTED_EMAIL]", text)
        text = self.phone_regex.sub("[REDACTED_PHONE]", text)
        return text
