from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

FSRS_VERSION_SEVEN = 0
FSRS7_SAME_DAY_OPTIMIZE_KEY = "fsrs7IncludeSameDayOptimize"
FSRS7_SAME_DAY_EVALUATE_KEY = "fsrs7IncludeSameDayEvaluate"
FSRS_VERSION_LABELS = {
    0: "7",
    1: "6",
    2: "5",
    3: "4",
}

_DESIRED_RETENTION_KEYS = ("desiredRetention", "desired_retention")
_FSRS_VERSION_KEYS = ("fsrsVersion", "fsrs_version")
_LEARNING_STEPS_KEYS = ("learnSteps", "learn_steps")
_RELEARNING_STEPS_KEYS = ("relearnSteps", "relearn_steps")
_LEARNING_STEPS_LEGACY_PATH = ("new", "delays")
_RELEARNING_STEPS_LEGACY_PATH = ("lapse", "delays")
_FSRS_PARAMS_BY_VERSION: dict[int, tuple[str, ...]] = {
    0: ("fsrsParams7", "fsrs_params_7", "fsrs_params7"),
    1: ("fsrsParams6", "fsrs_params_6", "fsrs_params6"),
    2: ("fsrsParams5", "fsrs_params_5", "fsrs_params5"),
    3: ("fsrsParams4", "fsrs_params_4", "fsrs_params4"),
}
_LEGACY_PARAM_KEYS = ("fsrsParams", "fsrs_params", "fsrsWeights", "fsrs_weights")
_UNVERSIONED_PARAM_KEYS = (
    "fsrsParams6",
    "fsrs_params_6",
    "fsrs_params6",
    "fsrsParams5",
    "fsrs_params_5",
    "fsrs_params5",
    "fsrsParams4",
    "fsrs_params_4",
    "fsrs_params4",
)


def field(obj: Any, name: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def set_field(obj: Any, names: Sequence[str], value: Any) -> None:
    if isinstance(obj, MutableMapping):
        target = next((name for name in names if name in obj), names[0])
        obj[target] = value
        return
    target = next((name for name in names if hasattr(obj, name)), names[0])
    setattr(obj, target, value)


def has_field(obj: Any, name: str) -> bool:
    if isinstance(obj, Mapping):
        return name in obj
    return hasattr(obj, name)


def int_field(obj: Any, names: Sequence[str]) -> int | None:
    for name in names:
        value = field(obj, name)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            text = str(value).upper()
            if "SEVEN" in text or text.endswith("_7"):
                return 0
            if "SIX" in text or text.endswith("_6"):
                return 1
            if "FIVE" in text or text.endswith("_5"):
                return 2
            if "FOUR" in text or text.endswith("_4"):
                return 3
    return None


def desired_retention(payload: Any) -> float | None:
    for key in _DESIRED_RETENTION_KEYS:
        value = field(payload, key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def set_desired_retention(payload: Any, value: float | None) -> None:
    stored = None if value is None else float(value)
    set_field(payload, _DESIRED_RETENTION_KEYS, stored)


def learning_steps(payload: Any) -> tuple[float, ...]:
    return step_list(payload, _LEARNING_STEPS_KEYS, _LEARNING_STEPS_LEGACY_PATH)


def set_learning_steps(payload: Any, steps: Sequence[float]) -> None:
    set_step_list(payload, _LEARNING_STEPS_KEYS, _LEARNING_STEPS_LEGACY_PATH, steps)


def relearning_steps(payload: Any) -> tuple[float, ...]:
    return step_list(payload, _RELEARNING_STEPS_KEYS, _RELEARNING_STEPS_LEGACY_PATH)


def set_relearning_steps(payload: Any, steps: Sequence[float]) -> None:
    set_step_list(payload, _RELEARNING_STEPS_KEYS, _RELEARNING_STEPS_LEGACY_PATH, steps)


def step_list(payload: Any, keys: Sequence[str], legacy_path: Sequence[str]) -> tuple[float, ...]:
    if nested_field_exists(payload, legacy_path):
        return _float_tuple(nested_field(payload, legacy_path))
    for key in keys:
        steps = _float_tuple(field(payload, key))
        if steps or field(payload, key) is not None:
            return steps
    return ()


def set_step_list(payload: Any, keys: Sequence[str], legacy_path: Sequence[str], steps: Sequence[float]) -> None:
    stored = [float(step) for step in steps]
    if nested_field_exists(payload, legacy_path):
        nested = nested_field(payload, legacy_path[:-1])
        set_field(nested, (legacy_path[-1],), stored)
        if isinstance(payload, MutableMapping):
            for key in keys:
                payload.pop(key, None)
        return
    set_field(payload, keys, stored)


def nested_field(obj: Any, path: Sequence[str]) -> Any:
    current = obj
    for name in path:
        current = field(current, name)
        if current is None:
            return None
    return current


def nested_field_exists(obj: Any, path: Sequence[str]) -> bool:
    current = obj
    for name in path:
        if not has_field(current, name):
            return False
        current = field(current, name)
        if current is None:
            return False
    return True


def format_steps(steps: Sequence[float]) -> str:
    return " ".join(format_step(step) for step in steps)


def format_step(step: float) -> str:
    seconds = round(float(step) * 60)
    if seconds == 0:
        return "0s"
    if seconds % 86400 == 0:
        return f"{seconds // 86400}d"
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def normalize_steps_text(value: str) -> str:
    return format_steps(parse_steps(value))


def parse_steps(value: str) -> tuple[float, ...]:
    text = value.strip()
    if not text:
        return ()
    steps: list[float] = []
    for part in text.split():
        step = step_to_minutes(part)
        if step:
            steps.append(step)
    return tuple(steps)


def step_to_minutes(text: str) -> float:
    match = re.search(r"(\d+)(.*)", text)
    if not match:
        return 0.0
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "s":
        seconds = amount
    elif unit == "h":
        seconds = amount * 3600
    elif unit == "d":
        seconds = amount * 86400
    else:
        seconds = amount * 60
    return min(seconds, 2**31) / 60


def fsrs_version(payload: Any) -> int | None:
    return int_field(payload, _FSRS_VERSION_KEYS)


def available_fsrs_versions(payload: Any) -> tuple[int, ...]:
    current = fsrs_version(payload)
    if current is None:
        return ()

    versions = {current, 0, 1}
    for version, keys in _FSRS_PARAMS_BY_VERSION.items():
        if any(field(payload, key) is not None for key in keys):
            versions.add(version)
    return tuple(sorted(versions))


def fsrs_version_label(version: int) -> str:
    return FSRS_VERSION_LABELS.get(version, str(version))


def set_fsrs_version(payload: Any, value: int) -> None:
    set_field(payload, _FSRS_VERSION_KEYS, int(value))


def selected_fsrs_params(payload: Any) -> tuple[float, ...]:
    version = fsrs_version(payload)
    keys = _FSRS_PARAMS_BY_VERSION.get(version, _UNVERSIONED_PARAM_KEYS)
    for key in keys + _LEGACY_PARAM_KEYS:
        params = _float_tuple(field(payload, key))
        if params:
            return params
    return ()


def set_selected_fsrs_params(payload: Any, params: Sequence[float]) -> None:
    version = fsrs_version(payload)
    keys = _FSRS_PARAMS_BY_VERSION.get(version, _UNVERSIONED_PARAM_KEYS)
    target_key = next((key for key in keys + _LEGACY_PARAM_KEYS if field(payload, key) is not None), None)
    if target_key is None:
        target_key = keys[0] if keys else _LEGACY_PARAM_KEYS[0]
    set_field(payload, (target_key,), [float(value) for value in params])


def format_fsrs_params(params: Sequence[float]) -> str:
    return ", ".join(format_param(value) for value in params)


def format_param(value: float) -> str:
    number = float(value)
    factor = 1000
    truncated = math.trunc(number * factor) / factor
    text = f"{truncated:.3f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def same_day_settings(payload: Any) -> tuple[bool | None, bool | None]:
    if fsrs_version(payload) != FSRS_VERSION_SEVEN:
        return None, None
    aux_data = read_aux_data(payload)
    return (
        _bool_or_default(aux_data.get(FSRS7_SAME_DAY_OPTIMIZE_KEY), False),
        _bool_or_default(aux_data.get(FSRS7_SAME_DAY_EVALUATE_KEY), False),
    )


def set_same_day_settings(
    payload: Any,
    *,
    include_optimize: bool,
    include_evaluate: bool,
) -> None:
    aux_data = dict(read_aux_data(payload))
    aux_data[FSRS7_SAME_DAY_OPTIMIZE_KEY] = bool(include_optimize)
    aux_data[FSRS7_SAME_DAY_EVALUATE_KEY] = bool(include_evaluate)
    write_aux_data(payload, aux_data)


def read_aux_data(payload: Any) -> Mapping[str, Any]:
    if isinstance(payload, Mapping):
        aux_data: dict[str, Any] = {}
        nested = payload.get("other")
        if isinstance(nested, Mapping):
            aux_data.update(nested)
        elif isinstance(nested, str) and nested:
            try:
                parsed = json.loads(nested)
            except ValueError:
                parsed = {}
            if isinstance(parsed, Mapping):
                aux_data.update(parsed)
        for key in (FSRS7_SAME_DAY_OPTIMIZE_KEY, FSRS7_SAME_DAY_EVALUATE_KEY):
            if key in payload:
                aux_data[key] = payload[key]
        return aux_data

    other = field(payload, "other")
    if isinstance(other, (bytes, bytearray)):
        try:
            other = other.decode("utf-8")
        except UnicodeDecodeError:
            return {}
    if isinstance(other, str) and other:
        try:
            parsed = json.loads(other)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, Mapping) else {}
    return {}


def write_aux_data(payload: Any, aux_data: Mapping[str, Any]) -> None:
    if isinstance(payload, MutableMapping):
        payload[FSRS7_SAME_DAY_OPTIMIZE_KEY] = bool(
            aux_data.get(FSRS7_SAME_DAY_OPTIMIZE_KEY, False)
        )
        payload[FSRS7_SAME_DAY_EVALUATE_KEY] = bool(
            aux_data.get(FSRS7_SAME_DAY_EVALUATE_KEY, False)
        )
        nested = payload.get("other")
        if isinstance(nested, MutableMapping):
            nested.pop(FSRS7_SAME_DAY_OPTIMIZE_KEY, None)
            nested.pop(FSRS7_SAME_DAY_EVALUATE_KEY, None)
        return
    current = getattr(payload, "other", b"")
    encoded = json.dumps(dict(aux_data), sort_keys=True).encode("utf-8")
    setattr(payload, "other", encoded if isinstance(current, (bytes, bytearray)) else encoded.decode("utf-8"))


def _float_tuple(values: Any) -> tuple[float, ...]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return ()
    try:
        return tuple(float(value) for value in values)
    except (TypeError, ValueError):
        return ()


def _bool_or_default(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default
