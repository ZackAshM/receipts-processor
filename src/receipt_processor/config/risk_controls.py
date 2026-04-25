"""Risk-control runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RiskControls:
    """Runtime controls for confidence-based routing."""

    route_low_confidence_to_review: bool = True
    minimum_auto_accept_confidence: float = 0.85
    require_manual_review_below: float = 0.70


def _coerce_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return default


def _coerce_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_risk_controls(config_file: Path | None) -> RiskControls:
    """Load risk controls from YAML with safe defaults."""
    default = RiskControls()
    if config_file is None or not config_file.exists():
        return default

    try:
        import yaml  # type: ignore
    except Exception:
        return default

    try:
        with config_file.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
    except Exception:
        return default

    controls = payload.get("controls", {}) if isinstance(payload, dict) else {}
    thresholds = payload.get("thresholds", {}) if isinstance(payload, dict) else {}

    return RiskControls(
        route_low_confidence_to_review=_coerce_bool(
            controls.get("route_low_confidence_to_review"),
            default.route_low_confidence_to_review,
        ),
        minimum_auto_accept_confidence=_coerce_float(
            thresholds.get("minimum_auto_accept_confidence"),
            default.minimum_auto_accept_confidence,
        ),
        require_manual_review_below=_coerce_float(
            thresholds.get("require_manual_review_below"),
            default.require_manual_review_below,
        ),
    )

