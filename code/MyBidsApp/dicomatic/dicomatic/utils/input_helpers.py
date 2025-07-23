"""
Generic console-input utilities.

Only user-interaction primitives live here so that business logic in CLI
commands remains testable.  All prompts add a leading blank line to keep
console output readable during long interactive sessions.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

import click

# -----------------------------------------------------------------------------#
# Public API                                                                    #
# -----------------------------------------------------------------------------#
def prompt_input(
    message: str,
    type: Any = str,  # noqa: A002 – mirrors click.prompt arg name
    choices: Optional[Iterable[str]] = None,
    default: Any = None,
    hide_input: bool = False,
    show_choices: bool = True,
) -> Any:
    """Display an interactive prompt and return validated input.

    Args:
        message: Core prompt text (without suffix or choice list).
        type: Desired Python type for casting the response. ``str`` by default.
        choices: Optional iterable of accepted string values.  When provided,
            the response must match one of these exactly.
        default: Default value returned when the input is empty.
        hide_input: Masks keystrokes (typical for passwords).
        show_choices: When ``True`` append ``(a, b, c)`` after *message*.

    Returns:
        The parsed value, already cast to *type* when requested.

    Notes:
        The function loops until valid input is received.  Any error messages
        are printed to stderr via :pymod:`click`.
    """
    prompt_suffix = "\n> "  # newline keeps choices on separate line
    choices_list = list(choices) if choices is not None else None

    while True:
        click.echo()  # blank line before every prompt for spacing

        # Build full prompt text with optional “(a, b, c)” suffix
        prompt_text = message
        if choices_list and show_choices:
            prompt_text += f" ({', '.join(str(c) for c in choices_list)})"

        raw = click.prompt(
            prompt_text,
            default=default,
            hide_input=hide_input,
            show_choices=False,  # custom rendering already handled
            prompt_suffix=prompt_suffix,
            type=str,
        )

        # Enforce choice membership if a list was supplied
        if choices_list:
            if raw not in choices_list:
                click.echo(f"[ERROR] {raw!r} is not one of {choices_list}", err=True)
                continue
            return raw  # no further processing in choice-mode

        # Attempt type conversion when a non-str type is requested
        if type is not str:
            try:
                return type(raw)
            except Exception as exc:  # noqa: BLE001 – broad on purpose for CLI
                click.echo(f"[ERROR] invalid input ({exc})", err=True)
                continue

        # No conversion requested → return raw string
        return raw
