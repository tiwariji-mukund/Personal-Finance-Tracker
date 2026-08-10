from contextvars import ContextVar, Token
from uuid import uuid4

_request_id: ContextVar[str | None] = ContextVar(
    'request_id',
    default=None
)

def generate_request_id() -> str:
    return str(uuid4())

def set_request_id(request_id: str) -> Token:
    return _request_id.set(request_id)

def reset_request_id(token: Token) -> None:
    _request_id.reset(token)

def get_request_id() -> str:
    request_id = _request_id.get()
    if not request_id:
        request_id = generate_request_id()
        set_request_id(request_id)
    return request_id

def clear_request_id() -> None:
    _request_id.set(None)