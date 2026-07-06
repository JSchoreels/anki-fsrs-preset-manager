from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import fsrs_preset_manager.gateway as gateway_module
from fsrs_preset_manager.gateway import (
    AnkiGateway,
    DEFAULT_DESIRED_RETENTION_MINIMUM,
    call_backend,
    compute_fsrs_params,
    configured_desired_retention_minimum,
    desired_retention_minimum,
    evaluate_params_legacy,
    ignore_revlogs_before_ms,
    include_same_day_evaluate,
    include_same_day_optimize,
    preset_search,
    relearning_steps_in_day,
)


class FakeResponse(dict):
    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def compute_fsrs_params(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(("compute", kwargs))
        return FakeResponse(params=[7.0, 8.0], fsrs_items=12)

    def evaluate_params_legacy(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(("evaluate", kwargs))
        return FakeResponse(log_loss=0.1234, rmse_bins=0.056)


class FakeRepeated(list):
    def extend(self, values: Any) -> None:
        super().extend(values)


class FakeComputeRequest:
    last: "FakeComputeRequest | None" = None

    def __init__(self) -> None:
        self.search = ""
        self.current_params = FakeRepeated()
        self.ignore_revlogs_before_ms = 0
        self.num_of_relearning_steps = 0
        self.health_check = False
        self.include_same_day_reviews = None
        self.fsrs_version = None

    def SerializeToString(self) -> bytes:
        FakeComputeRequest.last = self
        return b"compute-request"


class FakeComputeResponse:
    def __init__(self) -> None:
        self.params = FakeRepeated()
        self.fsrs_items = 0

    def ParseFromString(self, data: bytes) -> None:
        assert data == b"compute-response"
        self.params.extend([1.0, 2.0])
        self.fsrs_items = 44


class FakeEvaluateRequest:
    last: "FakeEvaluateRequest | None" = None

    def __init__(self) -> None:
        self.search = ""
        self.params = FakeRepeated()
        self.ignore_revlogs_before_ms = 0
        self.include_same_day_reviews = None

    def SerializeToString(self) -> bytes:
        FakeEvaluateRequest.last = self
        return b"evaluate-request"


class FakeEvaluateResponse:
    def __init__(self) -> None:
        self.log_loss = 0.0
        self.rmse_bins = 0.0

    def ParseFromString(self, data: bytes) -> None:
        assert data == b"evaluate-response"
        self.log_loss = 0.5
        self.rmse_bins = 0.25


class FakeSchedulerPb2:
    ComputeFsrsParamsRequest = FakeComputeRequest
    ComputeFsrsParamsResponse = FakeComputeResponse
    EvaluateParamsLegacyRequest = FakeEvaluateRequest
    EvaluateParamsResponse = FakeEvaluateResponse


class FakeMainComputeRequest:
    last: "FakeMainComputeRequest | None" = None

    def __init__(self) -> None:
        self.search = ""
        self.current_params = FakeRepeated()
        self.ignore_revlogs_before_ms = 0
        self.num_of_relearning_steps = 0
        self.health_check = False

    def SerializeToString(self) -> bytes:
        FakeMainComputeRequest.last = self
        return b"compute-request"


class FakeMainEvaluateRequest:
    last: "FakeMainEvaluateRequest | None" = None

    def __init__(self) -> None:
        self.search = ""
        self.params = FakeRepeated()
        self.ignore_revlogs_before_ms = 0

    def SerializeToString(self) -> bytes:
        FakeMainEvaluateRequest.last = self
        return b"evaluate-request"


class FakeMainSchedulerPb2:
    ComputeFsrsParamsRequest = FakeMainComputeRequest
    ComputeFsrsParamsResponse = FakeComputeResponse
    EvaluateParamsLegacyRequest = FakeMainEvaluateRequest
    EvaluateParamsResponse = FakeEvaluateResponse


class FakeRawBackend:
    def compute_fsrs_params_raw(self, data: bytes) -> bytes:
        assert data == b"compute-request"
        return b"compute-response"

    def evaluate_params_legacy_raw(self, data: bytes) -> bytes:
        assert data == b"evaluate-request"
        return b"evaluate-response"


class FakeDecks:
    def __init__(self) -> None:
        self.configs = [
            {
                "id": 10,
                "name": "Main preset",
                "desiredRetention": 0.9,
                "fsrsVersion": 0,
                "fsrsParams7": [1.0, 2.0],
                "new": {"delays": [1.0, 10.0]},
                "lapse": {"delays": [10.0]},
                "other": '{"fsrs7IncludeSameDayOptimize": false, "fsrs7IncludeSameDayEvaluate": true}',
            }
        ]
        self.decks = {
            100: {"id": 100, "name": "Japanese", "conf": 10, "dyn": 0},
            101: {"id": 101, "name": "Japanese::Grammar", "conf": 10, "dyn": 0, "desiredRetention": 0.87},
        }
        self.saved_configs: list[dict[str, Any]] = []
        self.saved_decks: list[dict[str, Any]] = []

    def all_config(self) -> list[dict[str, Any]]:
        return self.configs

    def all_names_and_ids(self, include_filtered: bool = True) -> list[SimpleNamespace]:
        return [SimpleNamespace(id=deck_id, name=deck["name"]) for deck_id, deck in self.decks.items()]

    def get(self, deck_id: int, default: bool = True) -> dict[str, Any] | None:
        return self.decks.get(deck_id)

    def all(self) -> list[dict[str, Any]]:
        return list(self.decks.values())

    def update_config(self, payload: dict[str, Any]) -> None:
        self.saved_configs.append(payload.copy())

    def update_dict(self, payload: dict[str, Any]) -> None:
        self.saved_decks.append(payload.copy())


class FakeMw:
    def __init__(self) -> None:
        self.col = SimpleNamespace(decks=FakeDecks(), _backend=FakeBackend(), db=FakeDb())
        self.addonManager = FakeAddonManager()
        self.reset_count = 0

    def reset(self) -> None:
        self.reset_count += 1


class FakeAddonManager:
    def __init__(self) -> None:
        self.config: dict[str, Any] = {}

    def getConfig(self, module: str) -> dict[str, Any]:
        return self.config


class FakeDb:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def scalar(self, query: str, *args: Any) -> int:
        self.calls.append((query, args))
        return 5


def test_load_presets_groups_decks_and_reads_settings() -> None:
    gateway = AnkiGateway(FakeMw())

    presets = gateway.load_presets()

    assert len(presets) == 1
    assert presets[0].fsrs_versions == (0, 1)
    assert presets[0].learning_steps == (1.0, 10.0)
    assert presets[0].relearning_steps == (10.0,)
    assert presets[0].include_same_day_optimize is False
    assert presets[0].include_same_day_evaluate is True
    assert [deck.name for deck in presets[0].decks] == ["Japanese", "Japanese::Grammar"]
    assert presets[0].decks[1].desired_retention == 0.87
    assert presets[0].review_count == 5


def test_load_presets_counts_reviews_for_assigned_decks() -> None:
    mw = FakeMw()

    AnkiGateway(mw).load_presets()

    query, args = mw.col.db.calls[-1]
    assert "revlog" in query
    assert "cards" in query
    assert args == (100, 101, 100, 101)


def test_desired_retention_minimum_falls_back_to_existing_lower_value() -> None:
    mw = FakeMw()
    mw.col.decks.configs[0]["desiredRetention"] = 0.05

    assert desired_retention_minimum(mw) == 0.05


def test_desired_retention_minimum_uses_existing_lower_deck_override() -> None:
    mw = FakeMw()
    mw.col.decks.decks[101]["desiredRetention"] = 0.2

    assert desired_retention_minimum(mw) == 0.2


def test_desired_retention_minimum_defaults_to_70_percent() -> None:
    assert desired_retention_minimum(FakeMw()) == DEFAULT_DESIRED_RETENTION_MINIMUM


def test_desired_retention_minimum_uses_config_override() -> None:
    mw = FakeMw()
    mw.addonManager.config["desired_retention_minimum"] = 0.25

    assert desired_retention_minimum(mw) == 0.25


def test_configured_desired_retention_minimum_ignores_invalid_config() -> None:
    mw = FakeMw()
    mw.addonManager.config["desired_retention_minimum"] = "invalid"

    assert configured_desired_retention_minimum(mw) == DEFAULT_DESIRED_RETENTION_MINIMUM


def test_save_deck_override_clears_to_none() -> None:
    mw = FakeMw()
    gateway = AnkiGateway(mw)
    deck = gateway.load_presets()[0].decks[1]

    gateway.save_deck_override(deck, None)

    assert mw.col.decks.saved_decks[-1]["desiredRetention"] is None


def test_save_preset_updates_learning_and_relearning_steps() -> None:
    mw = FakeMw()
    gateway = AnkiGateway(mw)
    preset = gateway.load_presets()[0]

    gateway.save_preset(
        preset,
        desired_retention_value=0.9,
        fsrs_version_value=0,
        learning_steps_value=(2.0, 15.0),
        relearning_steps_value=(20.0,),
        include_same_day_optimize=False,
        include_same_day_evaluate=True,
    )

    assert mw.col.decks.saved_configs[-1]["new"]["delays"] == [2.0, 15.0]
    assert mw.col.decks.saved_configs[-1]["lapse"]["delays"] == [20.0]


def test_optimize_preset_passes_same_day_flag_and_saves_params() -> None:
    mw = FakeMw()
    gateway = AnkiGateway(mw)
    preset = gateway.load_presets()[0]

    fsrs_items, params = gateway.optimize_preset(preset)

    assert fsrs_items == 12
    assert params == (7.0, 8.0)
    assert mw.col._backend.calls[-1][1]["include_same_day_reviews"] is False
    assert mw.col.decks.saved_configs[-1]["fsrsParams7"] == [7.0, 8.0]


def test_evaluate_preset_passes_same_day_flag_and_params() -> None:
    mw = FakeMw()
    gateway = AnkiGateway(mw)
    preset = gateway.load_presets()[0]

    log_loss, rmse_bins = gateway.evaluate_preset(preset)

    assert log_loss == 0.1234
    assert rmse_bins == 0.056
    assert mw.col._backend.calls[-1][1]["include_same_day_reviews"] is True
    assert mw.col._backend.calls[-1][1]["params"] == (1.0, 2.0)


def test_preset_search_uses_deck_query_when_param_search_missing() -> None:
    preset = AnkiGateway(FakeMw()).load_presets()[0]

    assert preset_search(preset) == 'deck:"Japanese" OR deck:"Japanese::Grammar"'


def test_call_backend_retries_with_camel_case_kwargs() -> None:
    class CamelBackend:
        def method(self, **kwargs: Any) -> dict[str, Any]:
            if "include_same_day_reviews" in kwargs:
                raise TypeError("camel only")
            return kwargs

    assert call_backend(
        CamelBackend(),
        "method",
        {"include_same_day_reviews": False},
    ) == {"includeSameDayReviews": False}


def test_ignore_revlogs_before_ms_matches_anki_date_conversion() -> None:
    assert ignore_revlogs_before_ms({"ignoreRevlogsBeforeDate": "2024-01-02"}) == 1704153600000


def test_include_same_day_helpers_read_current_payload_after_save() -> None:
    mw = FakeMw()
    gateway = AnkiGateway(mw)
    preset = gateway.load_presets()[0]

    gateway.save_preset(
        preset,
        desired_retention_value=0.9,
        fsrs_version_value=0,
        learning_steps_value=preset.learning_steps,
        relearning_steps_value=preset.relearning_steps,
        include_same_day_optimize=True,
        include_same_day_evaluate=False,
    )

    assert include_same_day_optimize(preset) is True
    assert include_same_day_evaluate(preset) is False


def test_save_preset_updates_fsrs_version_when_picker_is_supported() -> None:
    mw = FakeMw()
    gateway = AnkiGateway(mw)
    preset = gateway.load_presets()[0]

    gateway.save_preset(
        preset,
        desired_retention_value=0.9,
        fsrs_version_value=1,
        learning_steps_value=preset.learning_steps,
        relearning_steps_value=preset.relearning_steps,
        include_same_day_optimize=None,
        include_same_day_evaluate=None,
    )

    assert mw.col.decks.saved_configs[-1]["fsrsVersion"] == 1


def test_save_preset_does_not_create_fsrs_version_without_picker_support() -> None:
    mw = FakeMw()
    mw.col.decks.configs[0].pop("fsrsVersion")
    gateway = AnkiGateway(mw)
    preset = gateway.load_presets()[0]

    gateway.save_preset(
        preset,
        desired_retention_value=0.9,
        fsrs_version_value=0,
        learning_steps_value=preset.learning_steps,
        relearning_steps_value=preset.relearning_steps,
        include_same_day_optimize=None,
        include_same_day_evaluate=None,
    )

    assert "fsrsVersion" not in mw.col.decks.saved_configs[-1]


def test_optimize_uses_current_payload_fsrs_version_after_save() -> None:
    mw = FakeMw()
    mw.col.decks.configs[0]["fsrsParams6"] = [6.0]
    gateway = AnkiGateway(mw)
    preset = gateway.load_presets()[0]
    gateway.save_preset(
        preset,
        desired_retention_value=0.9,
        fsrs_version_value=1,
        learning_steps_value=preset.learning_steps,
        relearning_steps_value=preset.relearning_steps,
        include_same_day_optimize=None,
        include_same_day_evaluate=None,
    )

    gateway.optimize_preset(preset)

    assert mw.col._backend.calls[-1][1]["fsrs_version"] == 1
    assert mw.col._backend.calls[-1][1]["current_params"] == (6.0,)
    assert mw.col.decks.saved_configs[-1]["fsrsParams6"] == [7.0, 8.0]


def test_relearning_steps_in_day_counts_steps_before_one_day() -> None:
    assert relearning_steps_in_day({"lapse": {"delays": [10, 60, 1440, 5]}}) == 2


def test_compute_fsrs_params_uses_raw_protobuf_backend() -> None:
    gateway_module.SCHEDULER_PB2_OVERRIDE = FakeSchedulerPb2
    try:
        response = compute_fsrs_params(
            FakeRawBackend(),
            {
                "search": 'deck:"Japanese"',
                "current_params": (3.0, 4.0),
                "ignore_revlogs_before_ms": 123,
                "num_of_relearning_steps": 2,
                "health_check": False,
                "include_same_day_reviews": True,
                "fsrs_version": 0,
            },
        )
    finally:
        gateway_module.SCHEDULER_PB2_OVERRIDE = None

    assert response.params == [1.0, 2.0]
    assert response.fsrs_items == 44
    assert FakeComputeRequest.last is not None
    assert FakeComputeRequest.last.current_params == [3.0, 4.0]
    assert FakeComputeRequest.last.include_same_day_reviews is True


def test_evaluate_params_legacy_uses_raw_protobuf_backend() -> None:
    gateway_module.SCHEDULER_PB2_OVERRIDE = FakeSchedulerPb2
    try:
        response = evaluate_params_legacy(
            FakeRawBackend(),
            {
                "search": 'deck:"Japanese"',
                "params": (3.0, 4.0),
                "ignore_revlogs_before_ms": 123,
                "include_same_day_reviews": False,
            },
        )
    finally:
        gateway_module.SCHEDULER_PB2_OVERRIDE = None

    assert response.log_loss == 0.5
    assert response.rmse_bins == 0.25
    assert FakeEvaluateRequest.last is not None
    assert FakeEvaluateRequest.last.params == [3.0, 4.0]
    assert FakeEvaluateRequest.last.include_same_day_reviews is False


def test_raw_backend_skips_fields_missing_from_anki_main_requests() -> None:
    gateway_module.SCHEDULER_PB2_OVERRIDE = FakeMainSchedulerPb2
    try:
        compute_fsrs_params(
            FakeRawBackend(),
            {
                "search": 'deck:"Japanese"',
                "current_params": (3.0, 4.0),
                "ignore_revlogs_before_ms": 123,
                "num_of_relearning_steps": 2,
                "health_check": False,
                "include_same_day_reviews": True,
                "fsrs_version": 0,
            },
        )
        evaluate_params_legacy(
            FakeRawBackend(),
            {
                "search": 'deck:"Japanese"',
                "params": (3.0, 4.0),
                "ignore_revlogs_before_ms": 123,
                "include_same_day_reviews": False,
            },
        )
    finally:
        gateway_module.SCHEDULER_PB2_OVERRIDE = None

    assert FakeMainComputeRequest.last is not None
    assert not hasattr(FakeMainComputeRequest.last, "include_same_day_reviews")
    assert not hasattr(FakeMainComputeRequest.last, "fsrs_version")
    assert FakeMainComputeRequest.last.current_params == [3.0, 4.0]
    assert FakeMainEvaluateRequest.last is not None
    assert not hasattr(FakeMainEvaluateRequest.last, "include_same_day_reviews")
    assert FakeMainEvaluateRequest.last.params == [3.0, 4.0]
