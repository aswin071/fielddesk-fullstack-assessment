from contextvars import ContextVar, Token

correlation_id_context: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def set_correlation_id(value: str) -> Token:
    return correlation_id_context.set(value)


def reset_correlation_id(token: Token) -> None:
    correlation_id_context.reset(token)


def get_correlation_id() -> str | None:
    return correlation_id_context.get()

