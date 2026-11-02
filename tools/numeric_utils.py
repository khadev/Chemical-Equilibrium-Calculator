"""
tools/numeric_utils.py
=========================
Safe numeric parsing for UI input fields.

Every numeric entry in this application binds to a ``ctk.StringVar``
rather than ``ctk.DoubleVar``/``ctk.IntVar``. Tk's typed Variable
classes coerce to float/int *immediately* on every keystroke via their
own internal ``get()`` — including the instant an entry is temporarily
empty (e.g. the user selects-all and retypes a number), which raises
``_tkinter.TclError: expected floating-point number but got ""`` from
inside customtkinter's own entry-validation callback, before this
application's code ever runs. Using ``StringVar`` everywhere and
parsing explicitly (only when a value is actually needed, e.g. when
"Calculate" is clicked) avoids that entire class of crash.
"""
from __future__ import annotations

from typing import Union


def safe_float(value: Union[str, float, int, None], default: float = 0.0) -> float:
    """
    Parse ``value`` as a float, tolerating blank/partial/invalid input.

    Args:
        value: Raw value, typically a ``StringVar.get()`` result.
        default: Returned when parsing fails (e.g. empty string, a
            bare "-" or "." while the user is still typing).

    Returns:
        The parsed float, or ``default`` if parsing failed.
    """
    if value is None:
        return default
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def safe_int(value: Union[str, float, int, None], default: int = 0) -> int:
    """
    Parse ``value`` as an int, tolerating blank/partial/invalid input.

    Args:
        value: Raw value, typically a ``StringVar.get()`` result.
        default: Returned when parsing fails.

    Returns:
        The parsed int, or ``default`` if parsing failed.
    """
    if value is None:
        return default
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default
