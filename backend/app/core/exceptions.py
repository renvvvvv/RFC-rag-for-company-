"""Domain-level exceptions used across the RAG backend."""


class RAGBaseException(Exception):
    """Base exception for all RAG backend errors."""

    status_code: int = 500
    message: str = "Internal server error"

    def __init__(self, message: str | None = None, status_code: int | None = None):
        if message is not None:
            self.message = message
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)


class PermissionDeniedException(RAGBaseException):
    status_code: int = 403
    message: str = "Permission denied"


class NotFoundException(RAGBaseException):
    status_code: int = 404
    message: str = "Resource not found"


class ValidationException(RAGBaseException):
    status_code: int = 400
    message: str = "Validation error"


class AuthenticationException(RAGBaseException):
    status_code: int = 401
    message: str = "Authentication failed"


class ExternalAPIException(RAGBaseException):
    status_code: int = 502
    message: str = "External service unavailable"
