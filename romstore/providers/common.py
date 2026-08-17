from __future__ import annotations


class ProviderError(RuntimeError):
    """A catalog provider could not produce a trustworthy response."""


def optional_non_negative_int(value: object) -> int | None:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def positive_int_or(value: object, default: int) -> int:
    parsed = optional_non_negative_int(value)
    return parsed if parsed is not None and parsed > 0 else default
