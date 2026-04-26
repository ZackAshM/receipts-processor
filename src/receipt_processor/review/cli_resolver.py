"""CLI interactive handler for receipt review requests."""

from __future__ import annotations

from receipt_processor.review.models import (
    ReviewDecision,
    ReviewField,
    ReviewHandler,
    ReviewRequest,
)


def _print_field_header(field: ReviewField) -> None:
    print(f"\nResolve field: {field.display_name}")
    letter = ord("a")
    for option in field.options:
        source = option.source or "unknown"
        label = option.label or option.value
        print(f"  {chr(letter)}. (from {source}) {label}")
        letter += 1
    print("  m. Manual input")
    print("  s. Skip receipt")
    print("  x. Cancel run")


def _resolve_field(field: ReviewField) -> tuple[str, str] | ReviewDecision:
    while True:
        _print_field_header(field)
        choice = input("Choose an option: ").strip().lower()
        if choice == "m":
            manual = input(f"Enter value for {field.display_name}: ").strip()
            if manual:
                return field.name, manual
            print("Manual value cannot be empty.")
            continue
        if choice == "s":
            return ReviewDecision(action="skip_receipt")
        if choice == "x":
            return ReviewDecision(action="cancel_run")
        if len(choice) == 1 and "a" <= choice <= "z":
            idx = ord(choice) - ord("a")
            if 0 <= idx < len(field.options):
                selected = field.options[idx]
                return field.name, selected.value
        print("Invalid choice. Please choose one of the listed options.")


def create_cli_review_handler() -> ReviewHandler:
    """Return an interactive CLI review handler."""

    def handler(request: ReviewRequest) -> ReviewDecision:
        print("\n" + "=" * 72)
        print(f"User Review: {request.title}")
        print(f"Receipt: {request.receipt_filename}")
        print(request.message)
        resolved: dict[str, str] = {}

        for field in request.fields:
            result = _resolve_field(field)
            if isinstance(result, ReviewDecision):
                return result
            name, value = result
            resolved[name] = value

        return ReviewDecision(action="resolved", resolved_fields=resolved)

    return handler

