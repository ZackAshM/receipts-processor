"""Shared review request/decision models for CLI and GUI resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal


class RunCancelledError(Exception):
    """Raised when the user chooses to cancel the full run."""


@dataclass(frozen=True)
class ReviewOption:
    """One source-derived option for resolving a field."""

    source: str
    value: str
    label: str = ""


@dataclass(frozen=True)
class ReviewField:
    """A field the user can resolve, with source options and manual input."""

    name: str
    display_name: str
    options: list[ReviewOption] = field(default_factory=list)
    allow_manual: bool = True


@dataclass(frozen=True)
class ReviewRequest:
    """Interactive review payload shown to user in CLI/GUI."""

    issue_type: str
    title: str
    message: str
    receipt_filename: str
    fields: list[ReviewField]


@dataclass(frozen=True)
class ReviewDecision:
    """User decision result for a review prompt."""

    action: Literal["resolved", "skip_receipt", "cancel_run"]
    resolved_fields: dict[str, str] = field(default_factory=dict)


ReviewHandler = Callable[[ReviewRequest], ReviewDecision]

