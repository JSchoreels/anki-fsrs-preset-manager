from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from .fsrs_payload import (
    FSRS_VERSION_SEVEN,
    available_fsrs_versions,
    desired_retention,
    fsrs_version,
    learning_steps,
    relearning_steps,
    same_day_settings,
    selected_fsrs_params,
    set_desired_retention,
    set_fsrs_version,
    set_learning_steps,
    set_relearning_steps,
    set_same_day_settings,
    set_selected_fsrs_params,
)
from .models import DeckEntry, PresetEntry

LOGGER = logging.getLogger(__name__)
SCHEDULER_PB2_OVERRIDE: Any | None = None
DEFAULT_DESIRED_RETENTION_MINIMUM = 0.70
DESIRED_RETENTION_MINIMUM_CONFIG_KEY = "desired_retention_minimum"


class AnkiGateway:
    def __init__(self, mw: Any) -> None:
        self.mw = mw

    def load_presets(self) -> list[PresetEntry]:
        presets_by_id = {
            int(field(config, "id")): config
            for config in self.mw.col.decks.all_config()
            if field(config, "id") is not None
        }
        decks_by_preset: dict[int, list[DeckEntry]] = {preset_id: [] for preset_id in presets_by_id}

        for deck_id, deck_name in deck_entries(self.mw.col.decks):
            deck = self.mw.col.decks.get(deck_id, default=False)
            if not deck or field(deck, "dyn"):
                continue
            preset_id = int(field(deck, "conf") or 1)
            decks_by_preset.setdefault(preset_id, []).append(
                DeckEntry(
                    deck_id=deck_id,
                    name=deck_name,
                    preset_id=preset_id,
                    desired_retention=desired_retention(deck),
                    payload=deck,
                )
            )

        presets: list[PresetEntry] = []
        for preset_id, config in sorted(presets_by_id.items(), key=lambda item: str(field(item[1], "name"))):
            include_optimize, include_evaluate = same_day_settings(config)
            decks = tuple(sorted(decks_by_preset.get(preset_id, ()), key=lambda deck: deck.name))
            presets.append(
                PresetEntry(
                    preset_id=preset_id,
                    name=str(field(config, "name") or f"Preset {preset_id}"),
                    desired_retention=desired_retention(config),
                    fsrs_version=fsrs_version(config),
                    fsrs_versions=available_fsrs_versions(config),
                    learning_steps=learning_steps(config),
                    relearning_steps=relearning_steps(config),
                    include_same_day_optimize=include_optimize,
                    include_same_day_evaluate=include_evaluate,
                    params=selected_fsrs_params(config),
                    review_count=count_reviews_for_decks(self.mw.col, [deck.deck_id for deck in decks]),
                    payload=config,
                    decks=decks,
                )
            )
        return presets

    def desired_retention_minimum(self) -> float:
        return desired_retention_minimum(self.mw)

    def save_preset(
        self,
        preset: PresetEntry,
        *,
        desired_retention_value: float,
        fsrs_version_value: int | None,
        learning_steps_value: tuple[float, ...],
        relearning_steps_value: tuple[float, ...],
        include_same_day_optimize: bool | None,
        include_same_day_evaluate: bool | None,
    ) -> None:
        set_desired_retention(preset.payload, desired_retention_value)
        set_learning_steps(preset.payload, learning_steps_value)
        set_relearning_steps(preset.payload, relearning_steps_value)
        if preset.fsrs_versions and fsrs_version_value is not None:
            set_fsrs_version(preset.payload, fsrs_version_value)
        if (
            fsrs_version(preset.payload) == FSRS_VERSION_SEVEN
            and include_same_day_optimize is not None
            and include_same_day_evaluate is not None
        ):
            set_same_day_settings(
                preset.payload,
                include_optimize=include_same_day_optimize,
                include_evaluate=include_same_day_evaluate,
            )
        self.mw.col.decks.update_config(preset.payload)
        LOGGER.info(
            "saved preset fsrs settings preset_id=%s fsrs_version=%s learning_steps=%s relearning_steps=%s",
            preset.preset_id,
            fsrs_version(preset.payload),
            len(learning_steps_value),
            len(relearning_steps_value),
        )

    def save_deck_override(self, deck: DeckEntry, desired_retention_value: float | None) -> None:
        set_desired_retention(deck.payload, desired_retention_value)
        self.mw.col.decks.update_dict(deck.payload)
        LOGGER.info("saved deck desired retention override deck_id=%s has_override=%s", deck.deck_id, desired_retention_value is not None)

    def optimize_preset(self, preset: PresetEntry) -> tuple[int, tuple[float, ...]]:
        request = self._fsrs_request_kwargs(preset, include_same_day=include_same_day_optimize(preset))
        response = compute_fsrs_params(self.mw.col._backend, request)
        params = float_tuple_field(response, "params")
        fsrs_items = int_field(response, "fsrs_items", "fsrsItems")
        if params:
            set_selected_fsrs_params(preset.payload, params)
            self.mw.col.decks.update_config(preset.payload)
            LOGGER.info("optimized preset preset_id=%s fsrs_items=%s param_count=%s", preset.preset_id, fsrs_items, len(params))
        return fsrs_items, params

    def evaluate_preset(self, preset: PresetEntry) -> tuple[float, float]:
        request = self._fsrs_request_kwargs(
            preset,
            include_same_day=include_same_day_evaluate(preset),
            params=selected_fsrs_params(preset.payload),
        )
        response = evaluate_params_legacy(self.mw.col._backend, request)
        log_loss = float_field(response, "log_loss", "logLoss")
        rmse_bins = float_field(response, "rmse_bins", "rmseBins")
        LOGGER.info("evaluated preset preset_id=%s log_loss=%.4f rmse_bins=%.4f", preset.preset_id, log_loss, rmse_bins)
        return log_loss, rmse_bins

    def _fsrs_request_kwargs(
        self,
        preset: PresetEntry,
        *,
        include_same_day: bool | None,
        params: tuple[float, ...] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "search": preset_search(preset),
            "ignore_revlogs_before_ms": ignore_revlogs_before_ms(preset.payload),
        }
        if params is None:
            current_version = fsrs_version(preset.payload)
            kwargs["current_params"] = selected_fsrs_params(preset.payload)
            kwargs["num_of_relearning_steps"] = relearning_steps_in_day(preset.payload)
            kwargs["health_check"] = False
            if current_version is not None:
                kwargs["fsrs_version"] = current_version
        else:
            kwargs["params"] = tuple(params)
        if include_same_day is not None:
            kwargs["include_same_day_reviews"] = include_same_day
        return kwargs


def include_same_day_optimize(preset: PresetEntry) -> bool | None:
    if fsrs_version(preset.payload) != FSRS_VERSION_SEVEN:
        return None
    optimize, _ = same_day_settings(preset.payload)
    return optimize


def include_same_day_evaluate(preset: PresetEntry) -> bool | None:
    if fsrs_version(preset.payload) != FSRS_VERSION_SEVEN:
        return None
    _, evaluate = same_day_settings(preset.payload)
    return evaluate


def deck_entries(deck_manager: Any) -> list[tuple[int, str]]:
    entries = []
    for item in deck_manager.all_names_and_ids(include_filtered=False):
        if isinstance(item, Mapping):
            entries.append((int(item["id"]), str(item["name"])))
        else:
            entries.append((int(getattr(item, "id")), str(getattr(item, "name"))))
    return entries


def count_reviews_for_decks(col: Any, deck_ids: list[int]) -> int:
    if not deck_ids:
        return 0
    placeholders = ",".join("?" for _ in deck_ids)
    query = (
        "select count() from revlog r "
        "join cards c on c.id = r.cid "
        f"where c.did in ({placeholders}) or c.odid in ({placeholders})"
    )
    return int(col.db.scalar(query, *(deck_ids + deck_ids)) or 0)


def desired_retention_minimum(mw: Any) -> float:
    configured = configured_desired_retention_minimum(mw)
    existing = existing_desired_retention_minimum(mw)
    if existing is not None and existing < configured:
        return existing

    return configured


def configured_desired_retention_minimum(mw: Any) -> float:
    addon_manager = getattr(mw, "addonManager", None)
    get_config = getattr(addon_manager, "getConfig", None)
    if not callable(get_config):
        return DEFAULT_DESIRED_RETENTION_MINIMUM

    config = get_config(__name__.split(".", maxsplit=1)[0]) or {}
    try:
        return float(config.get(DESIRED_RETENTION_MINIMUM_CONFIG_KEY, DEFAULT_DESIRED_RETENTION_MINIMUM))
    except (TypeError, ValueError):
        LOGGER.warning(
            "invalid desired retention minimum config value=%r",
            config.get(DESIRED_RETENTION_MINIMUM_CONFIG_KEY),
        )
        return DEFAULT_DESIRED_RETENTION_MINIMUM


def existing_desired_retention_minimum(mw: Any) -> float | None:
    values: list[float] = []
    try:
        configs = mw.col.decks.all_config()
    except Exception:
        configs = []
    for config in configs:
        value = desired_retention(config)
        if value is not None:
            values.append(value)
    try:
        decks = mw.col.decks.all()
    except Exception:
        decks = []
    for deck in decks:
        value = desired_retention(deck)
        if value is not None:
            values.append(value)
    return min(values) if values else None


def preset_search(preset: PresetEntry) -> str:
    search = field(preset.payload, "paramSearch") or field(preset.payload, "param_search")
    if isinstance(search, str) and search.strip():
        return search.strip()
    return " OR ".join(f'deck:"{deck.name}"' for deck in preset.decks)


def ignore_revlogs_before_ms(payload: Any) -> int:
    date_value = field(payload, "ignoreRevlogsBeforeDate") or field(payload, "ignore_revlogs_before_date")
    if not isinstance(date_value, str) or not date_value:
        return 0
    parsed = datetime.strptime(date_value, "%Y-%m-%d")
    return int(parsed.replace(tzinfo=timezone.utc).timestamp() * 1000)


def relearning_steps_in_day(payload: Any) -> int:
    total_minutes = 0.0
    count = 0
    for step in relearning_steps(payload):
        total_minutes += step
        if total_minutes >= 1440:
            break
        count += 1
    return count


def call_backend(backend: Any, method_name: str, kwargs: dict[str, Any]) -> Any:
    method = getattr(backend, method_name)
    try:
        return method(**kwargs)
    except TypeError:
        camel_kwargs = {snake_to_camel(key): value for key, value in kwargs.items()}
        return method(**camel_kwargs)


def compute_fsrs_params(backend: Any, kwargs: dict[str, Any]) -> Any:
    raw_method = getattr(backend, "compute_fsrs_params_raw", None)
    if raw_method is not None:
        pb2 = scheduler_pb2()
        request = pb2.ComputeFsrsParamsRequest()
        assign_request_fields(request, kwargs)
        response = pb2.ComputeFsrsParamsResponse()
        response.ParseFromString(raw_method(request.SerializeToString()))
        return response
    return call_backend(backend, "compute_fsrs_params", kwargs)


def evaluate_params_legacy(backend: Any, kwargs: dict[str, Any]) -> Any:
    raw_method = getattr(backend, "evaluate_params_legacy_raw", None)
    if raw_method is not None:
        pb2 = scheduler_pb2()
        request = pb2.EvaluateParamsLegacyRequest()
        assign_request_fields(request, kwargs)
        response = pb2.EvaluateParamsResponse()
        response.ParseFromString(raw_method(request.SerializeToString()))
        return response
    return call_backend(backend, "evaluate_params_legacy", kwargs)


def assign_request_fields(request: Any, kwargs: dict[str, Any]) -> None:
    for key, value in kwargs.items():
        if value is None:
            continue
        if not hasattr(request, key):
            LOGGER.debug("skipping unsupported backend request field %s", key)
            continue
        if key in {"current_params", "params"}:
            getattr(request, key).extend(float(item) for item in value)
        else:
            setattr(request, key, value)


def scheduler_pb2() -> Any:
    if SCHEDULER_PB2_OVERRIDE is not None:
        return SCHEDULER_PB2_OVERRIDE
    from anki import scheduler_pb2 as pb2

    return pb2


def float_tuple_field(response: Any, name: str) -> tuple[float, ...]:
    values = field(response, name)
    if values is None:
        return ()
    return tuple(float(value) for value in values)


def int_field(response: Any, *names: str) -> int:
    for name in names:
        value = field(response, name)
        if value is not None:
            return int(value)
    return 0


def float_field(response: Any, *names: str) -> float:
    for name in names:
        value = field(response, name)
        if value is not None:
            return float(value)
    return 0.0


def snake_to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


def field(obj: Any, name: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)
