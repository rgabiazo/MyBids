"""Utility functions to print formatted CLI messages for progress updates."""

from __future__ import annotations

import click

__all__ = ["echo_banner", "echo_subject_session", "echo_success", "echo_section"]


def echo_banner(text: str) -> None:
    """Print a colourful banner announcing a processing step.

    Args:
        text: Banner text.
    """
    click.secho(f"\n=== {text} ===", fg="cyan")


def echo_subject_session(sub: str, ses: str | None = None) -> None:
    """Echo a bullet with subject/session information.

    Args:
        sub: Subject identifier.
        ses: Optional session identifier.
    """
    if ses:
        click.echo(f"  • {sub}/{ses}")
    else:
        click.echo(f"  • {sub}")


def echo_success(text: str) -> None:
    """Echo a green success message prefixed with a tick.

    Args:
        text: Message to display.
    """
    click.secho(f"✓ {text}", fg="green")


def echo_section(text: str) -> None:
    """Echo a purple section header used for modality blocks.

    Args:
        text: Section label.
    """
    click.secho(f"\n  — {text} —", fg="magenta")
