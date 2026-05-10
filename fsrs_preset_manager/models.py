from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DeckEntry:
    deck_id: int
    name: str
    preset_id: int
    desired_retention: float | None
    payload: Any


@dataclass(frozen=True)
class PresetEntry:
    preset_id: int
    name: str
    desired_retention: float | None
    fsrs_version: int | None
    fsrs_versions: tuple[int, ...]
    include_same_day_optimize: bool | None
    include_same_day_evaluate: bool | None
    params: tuple[float, ...]
    review_count: int
    payload: Any
    decks: tuple[DeckEntry, ...]
