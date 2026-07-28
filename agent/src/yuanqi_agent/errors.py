from typing import Any


class AgentError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 400, details: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class JavaApiError(AgentError):
    pass


class ThreadConflictError(AgentError):
    pass


class ThreadAccessDeniedError(AgentError):
    pass
