from __future__ import annotations

import json
from types import SimpleNamespace

from fsrs_preset_manager.fsrs_payload import (
    FSRS7_SAME_DAY_EVALUATE_KEY,
    FSRS7_SAME_DAY_OPTIMIZE_KEY,
    available_fsrs_versions,
    desired_retention,
    format_fsrs_params,
    fsrs_version,
    same_day_settings,
    selected_fsrs_params,
    set_desired_retention,
    set_fsrs_version,
    set_same_day_settings,
    set_selected_fsrs_params,
)


def test_desired_retention_reads_and_writes_existing_key() -> None:
    payload = {"desiredRetention": 0.91}

    assert desired_retention(payload) == 0.91

    set_desired_retention(payload, 0.86)

    assert payload["desiredRetention"] == 0.86


def test_desired_retention_writes_none_for_deck_override_clear() -> None:
    payload = {"desiredRetention": 0.88}

    set_desired_retention(payload, None)

    assert payload["desiredRetention"] is None


def test_same_day_settings_default_to_disabled_for_fsrs7() -> None:
    payload = {"fsrsVersion": 0}

    assert same_day_settings(payload) == (False, False)


def test_same_day_settings_read_top_level_legacy_keys() -> None:
    payload = {
        "fsrsVersion": 0,
        FSRS7_SAME_DAY_OPTIMIZE_KEY: False,
        FSRS7_SAME_DAY_EVALUATE_KEY: True,
    }

    assert same_day_settings(payload) == (False, True)


def test_same_day_settings_read_nested_json_other_for_proto_like_payloads() -> None:
    payload = {
        "fsrsVersion": 0,
        "other": json.dumps(
            {
                FSRS7_SAME_DAY_OPTIMIZE_KEY: False,
                FSRS7_SAME_DAY_EVALUATE_KEY: True,
            }
        ),
    }

    assert same_day_settings(payload) == (False, True)


def test_same_day_settings_are_hidden_for_non_fsrs7() -> None:
    payload = {"fsrsVersion": 1, "other": {FSRS7_SAME_DAY_OPTIMIZE_KEY: False}}

    assert same_day_settings(payload) == (None, None)


def test_available_fsrs_versions_are_hidden_without_picker_field() -> None:
    payload = {"fsrsParams6": [1, 2]}

    assert available_fsrs_versions(payload) == ()


def test_available_fsrs_versions_include_default_and_payload_param_versions() -> None:
    payload = {"fsrsVersion": 1, "fsrsParams5": [1, 2]}

    assert available_fsrs_versions(payload) == (0, 1, 2)


def test_set_fsrs_version_updates_existing_picker_field() -> None:
    payload = {"fsrsVersion": 1}

    set_fsrs_version(payload, 0)

    assert fsrs_version(payload) == 0
    assert payload["fsrsVersion"] == 0


def test_set_same_day_settings_updates_top_level_legacy_keys() -> None:
    payload = {"fsrsVersion": 0, "other": "{}"}

    set_same_day_settings(payload, include_optimize=False, include_evaluate=True)

    assert payload[FSRS7_SAME_DAY_OPTIMIZE_KEY] is False
    assert payload[FSRS7_SAME_DAY_EVALUATE_KEY] is True
    assert payload["other"] == "{}"


def test_set_same_day_settings_removes_stale_nested_legacy_keys() -> None:
    payload = {
        "fsrsVersion": 0,
        "other": {
            FSRS7_SAME_DAY_OPTIMIZE_KEY: False,
            FSRS7_SAME_DAY_EVALUATE_KEY: False,
        },
    }

    set_same_day_settings(payload, include_optimize=True, include_evaluate=True)

    assert payload[FSRS7_SAME_DAY_OPTIMIZE_KEY] is True
    assert payload[FSRS7_SAME_DAY_EVALUATE_KEY] is True
    assert FSRS7_SAME_DAY_OPTIMIZE_KEY not in payload["other"]
    assert FSRS7_SAME_DAY_EVALUATE_KEY not in payload["other"]


def test_selected_params_use_current_fsrs_version() -> None:
    payload = {"fsrsVersion": 0, "fsrsParams7": [1, 2], "fsrsParams6": [3]}

    assert selected_fsrs_params(payload) == (1.0, 2.0)


def test_selected_params_without_version_uses_anki_main_order() -> None:
    payload = {"fsrsParams4": [4], "fsrsParams5": [5], "fsrsParams6": [6]}

    assert selected_fsrs_params(payload) == (6.0,)


def test_selected_params_without_version_falls_back_to_fsrs5_then_fsrs4() -> None:
    assert selected_fsrs_params({"fsrsParams4": [4], "fsrsParams5": [5]}) == (5.0,)
    assert selected_fsrs_params({"fsrsParams4": [4]}) == (4.0,)


def test_format_fsrs_params_uses_selected_float_values() -> None:
    assert format_fsrs_params((1, 2.5, 0.123456789, -0.987654)) == "1, 2.5, 0.123, -0.987"


def test_set_selected_params_preserves_current_param_key() -> None:
    payload = {"fsrsVersion": 0, "fsrsParams7": [1, 2]}

    set_selected_fsrs_params(payload, [4, 5])

    assert payload["fsrsParams7"] == [4.0, 5.0]


def test_payload_helpers_support_objects() -> None:
    payload = SimpleNamespace(fsrs_version=0, other=b"{}")

    set_same_day_settings(payload, include_optimize=True, include_evaluate=False)

    assert same_day_settings(payload) == (True, False)
