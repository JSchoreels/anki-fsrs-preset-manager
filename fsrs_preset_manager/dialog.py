from __future__ import annotations

from typing import Any

from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    Qt,
)
from aqt.utils import showInfo, showWarning

from .fsrs_payload import format_fsrs_params, fsrs_version_label
from .gateway import AnkiGateway
from .models import DeckEntry, PresetEntry

COL_NAME = 0
COL_FSRS = 1
COL_RETENTION = 2
COL_OVERRIDE = 3
COL_OPTIMIZE_SAME_DAY = 4
COL_EVALUATE_SAME_DAY = 5
COL_OPTIMIZE = 6
COL_EVALUATE = 7
COL_DECK_OPTIONS = 8
COL_PARAMS = 9


class SortableTreeWidgetItem(QTreeWidgetItem):
    def __init__(self, parent: QTreeWidget | QTreeWidgetItem) -> None:
        super().__init__(parent)
        self._sort_values: dict[int, Any] = {}

    def set_sort_value(self, column: int, value: Any) -> None:
        self._sort_values[column] = value

    def __lt__(self, other: QTreeWidgetItem) -> bool:
        tree = self.treeWidget()
        column = tree.sortColumn() if tree else COL_NAME
        left = self._sort_key(column)
        if isinstance(other, SortableTreeWidgetItem):
            right = other._sort_key(column)
        else:
            right = normalize_sort_value(other.text(column))
        return left < right

    def _sort_key(self, column: int) -> tuple[int, Any]:
        return normalize_sort_value(
            self._sort_values.get(column, self.text(column).casefold())
        )


class FsrsPresetManagerDialog(QDialog):
    def __init__(self, mw: Any, gateway: AnkiGateway | None = None) -> None:
        super().__init__(mw)
        self.mw = mw
        self.gateway = gateway or AnkiGateway(mw)
        self.presets: list[PresetEntry] = []
        self.desired_retention_minimum = self.gateway.desired_retention_minimum()
        self._preset_widgets: dict[int, tuple[QComboBox | None, QDoubleSpinBox, QCheckBox | None, QCheckBox | None]] = {}
        self._preset_items: dict[int, SortableTreeWidgetItem] = {}
        self._deck_widgets: dict[int, tuple[DeckEntry, QCheckBox, QDoubleSpinBox]] = {}
        self.setWindowTitle("FSRS Preset Manager")
        self.resize(980, 640)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.show_decks = QCheckBox("Show decks")
        self.show_decks.setChecked(False)
        self.show_decks.stateChanged.connect(lambda _: self.refresh())
        self.hide_empty_presets = QCheckBox("Hide empty presets")
        self.hide_empty_presets.setChecked(True)
        self.hide_empty_presets.stateChanged.connect(lambda _: self.refresh())
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)
        toolbar.addWidget(self.show_decks)
        toolbar.addWidget(self.hide_empty_presets)
        toolbar.addStretch()
        self.default_fsrs_label = QLabel("Default FSRS")
        self.default_fsrs = QComboBox()
        self.apply_default_fsrs_button = QPushButton("Apply FSRS to All Presets")
        self.apply_default_fsrs_button.clicked.connect(self.apply_default_fsrs_to_presets)
        toolbar.addWidget(self.default_fsrs_label)
        toolbar.addWidget(self.default_fsrs)
        toolbar.addWidget(self.apply_default_fsrs_button)
        toolbar.addWidget(QLabel("Default DR"))
        self.default_retention = retention_spin(0.9, self.desired_retention_minimum)
        apply_default_button = QPushButton("Apply DR to All Presets")
        apply_default_button.clicked.connect(self.apply_default_retention_to_presets)
        toolbar.addWidget(self.default_retention)
        toolbar.addWidget(apply_default_button)
        toolbar.addWidget(refresh_button)
        root.addLayout(toolbar)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(10)
        self.tree.setHeaderLabels(
            [
                "Preset / deck",
                "FSRS",
                "Desired retention",
                "Deck Override",
                "FSRS-7 optimize same-day",
                "FSRS-7 evaluate same-day",
                "Optimize",
                "Evaluate",
                "Deck options",
                "FSRS params",
            ]
        )
        self.tree.setRootIsDecorated(True)
        self.tree.setSortingEnabled(True)
        root.addWidget(self.tree)

        buttons = QHBoxLayout()
        buttons.addStretch()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_all)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        buttons.addWidget(save_button)
        buttons.addWidget(close_button)
        root.addLayout(buttons)

    def refresh(self) -> None:
        sort_column = self.tree.sortColumn()
        sort_order = self.tree.header().sortIndicatorOrder()
        self.presets = self._filtered_presets(self.gateway.load_presets())
        self._preset_widgets.clear()
        self._preset_items.clear()
        self._deck_widgets.clear()
        self.tree.setSortingEnabled(False)
        self.tree.clear()
        show_same_day_columns = any(
            preset.include_same_day_optimize is not None
            or preset.include_same_day_evaluate is not None
            for preset in self.presets
        )
        available_fsrs_versions = sorted(
            {version for preset in self.presets for version in preset.fsrs_versions}
        )
        show_fsrs_column = bool(available_fsrs_versions)
        self._update_default_fsrs_options(available_fsrs_versions)
        self._set_default_fsrs_visible(show_fsrs_column)
        self.tree.setColumnHidden(COL_FSRS, not show_fsrs_column)
        self.tree.setColumnHidden(COL_OPTIMIZE_SAME_DAY, not show_same_day_columns)
        self.tree.setColumnHidden(COL_EVALUATE_SAME_DAY, not show_same_day_columns)
        self.tree.setColumnHidden(COL_OVERRIDE, not self.show_decks.isChecked())

        for preset in self.presets:
            item = SortableTreeWidgetItem(self.tree)
            item.setText(COL_NAME, preset.name)
            item.set_sort_value(COL_NAME, preset.name.casefold())
            item.setData(COL_NAME, Qt.ItemDataRole.UserRole, preset.preset_id)
            self._preset_items[preset.preset_id] = item

            fsrs_combo = None
            if preset.fsrs_versions:
                fsrs_combo = fsrs_version_combo(preset.fsrs_versions, preset.fsrs_version)
                item.setText(COL_FSRS, fsrs_version_label(selected_combo_data(fsrs_combo) or 0))
                item.set_sort_value(COL_FSRS, selected_combo_data(fsrs_combo))
                self.tree.setItemWidget(item, COL_FSRS, fsrs_combo)

            retention = retention_spin(preset.desired_retention or 0.9, self.desired_retention_minimum)
            item.setText(COL_RETENTION, f"{retention.value():.2f}")
            item.set_sort_value(COL_RETENTION, retention.value())
            self.tree.setItemWidget(item, COL_RETENTION, retention)

            params_text = format_fsrs_params(preset.params)
            item.setText(COL_PARAMS, params_text)
            item.set_sort_value(COL_PARAMS, tuple(preset.params))
            self.tree.setItemWidget(item, COL_PARAMS, params_line(params_text))

            optimize_same_day = None
            evaluate_same_day = None
            if preset.include_same_day_optimize is not None:
                optimize_same_day = checkbox(preset.include_same_day_optimize)
                item.set_sort_value(COL_OPTIMIZE_SAME_DAY, optimize_same_day.isChecked())
                self.tree.setItemWidget(item, COL_OPTIMIZE_SAME_DAY, center_widget(optimize_same_day))
            if preset.include_same_day_evaluate is not None:
                evaluate_same_day = checkbox(preset.include_same_day_evaluate)
                item.set_sort_value(COL_EVALUATE_SAME_DAY, evaluate_same_day.isChecked())
                self.tree.setItemWidget(item, COL_EVALUATE_SAME_DAY, center_widget(evaluate_same_day))

            optimize_button = QPushButton("Optimize")
            optimize_button.clicked.connect(lambda _, current=preset: self.optimize(current))
            evaluate_button = QPushButton("Evaluate")
            evaluate_button.clicked.connect(lambda _, current=preset: self.evaluate(current))
            deck_options_button = QPushButton("Deck Options")
            deck_options_button.setEnabled(bool(preset.decks))
            deck_options_button.clicked.connect(lambda _, current=preset: self.open_deck_options(current))
            if not preset.decks:
                deck_options_button.setToolTip("No deck currently uses this preset.")
            item.setText(COL_OPTIMIZE, "Optimize")
            item.setText(COL_EVALUATE, "Evaluate")
            item.setText(COL_DECK_OPTIONS, "Deck Options")
            self.tree.setItemWidget(item, COL_OPTIMIZE, optimize_button)
            self.tree.setItemWidget(item, COL_EVALUATE, evaluate_button)
            self.tree.setItemWidget(item, COL_DECK_OPTIONS, deck_options_button)
            self._preset_widgets[preset.preset_id] = (fsrs_combo, retention, optimize_same_day, evaluate_same_day)

            if self.show_decks.isChecked():
                for deck in preset.decks:
                    child = SortableTreeWidgetItem(item)
                    child.setText(COL_NAME, deck.name)
                    child.set_sort_value(COL_NAME, deck.name.casefold())
                    override = checkbox(deck.desired_retention is not None)
                    deck_retention = retention_spin(
                        deck.desired_retention or preset.desired_retention or 0.9,
                        self.desired_retention_minimum,
                    )
                    deck_retention.setEnabled(override.isChecked())
                    override.stateChanged.connect(lambda _, spin=deck_retention, current=override: spin.setEnabled(current.isChecked()))
                    child.setText(COL_RETENTION, f"{deck_retention.value():.2f}")
                    child.set_sort_value(COL_RETENTION, deck_retention.value())
                    child.set_sort_value(COL_OVERRIDE, override.isChecked())
                    self.tree.setItemWidget(child, COL_RETENTION, deck_retention)
                    self.tree.setItemWidget(child, COL_OVERRIDE, center_widget(override))
                    self._deck_widgets[deck.deck_id] = (deck, override, deck_retention)
                item.setExpanded(True)

        for column in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(column)
        self.tree.setSortingEnabled(True)
        self.tree.sortItems(sort_column, sort_order)

    def _filtered_presets(self, presets: list[PresetEntry]) -> list[PresetEntry]:
        if not self.hide_empty_presets.isChecked():
            return presets
        return [
            preset
            for preset in presets
            if preset.decks and preset.review_count > 0
        ]

    def apply_default_retention_to_presets(self) -> None:
        value = self.default_retention.value()
        for preset_id, widgets in self._preset_widgets.items():
            _, retention, _, _ = widgets
            retention.setValue(value)
            item = self._preset_items.get(preset_id)
            if item is not None:
                item.setText(COL_RETENTION, f"{value:.2f}")
                item.set_sort_value(COL_RETENTION, value)
        self.tree.sortItems(self.tree.sortColumn(), self.tree.header().sortIndicatorOrder())

    def apply_default_fsrs_to_presets(self) -> None:
        value = selected_combo_data(self.default_fsrs)
        if value is None:
            return
        for preset_id, widgets in self._preset_widgets.items():
            fsrs_combo, _, _, _ = widgets
            if fsrs_combo is None:
                continue
            index = fsrs_combo.findData(value)
            if index < 0:
                continue
            fsrs_combo.setCurrentIndex(index)
            item = self._preset_items.get(preset_id)
            if item is not None:
                item.setText(COL_FSRS, fsrs_version_label(value))
                item.set_sort_value(COL_FSRS, value)
        self.tree.sortItems(self.tree.sortColumn(), self.tree.header().sortIndicatorOrder())

    def save_all(self, *, show_message: bool = True, refresh: bool = True) -> bool:
        try:
            for preset in self.presets:
                fsrs_combo, retention, optimize_same_day, evaluate_same_day = self._preset_widgets[preset.preset_id]
                self.gateway.save_preset(
                    preset,
                    desired_retention_value=retention.value(),
                    fsrs_version_value=selected_combo_data(fsrs_combo) if fsrs_combo else None,
                    include_same_day_optimize=optimize_same_day.isChecked() if optimize_same_day else None,
                    include_same_day_evaluate=evaluate_same_day.isChecked() if evaluate_same_day else None,
                )
            for deck, override, retention in self._deck_widgets.values():
                self.gateway.save_deck_override(deck, retention.value() if override.isChecked() else None)
            self.mw.reset()
            if show_message:
                showInfo("FSRS preset settings saved.", parent=self)
            if refresh:
                self.refresh()
            return True
        except Exception as exc:
            showWarning(f"Unable to save FSRS preset settings:\n{exc}", parent=self)
            return False

    def optimize(self, preset: PresetEntry) -> None:
        if not self.save_all(show_message=False, refresh=False):
            return
        try:
            fsrs_items, params = self.gateway.optimize_preset(preset)
            if params:
                self.mw.reset()
                showInfo(f"Optimized {preset.name} with {fsrs_items} FSRS items.", parent=self)
                self.refresh()
            else:
                showInfo(f"No optimized parameters returned for {preset.name}.", parent=self)
        except Exception as exc:
            showWarning(f"Unable to optimize {preset.name}:\n{exc}", parent=self)

    def evaluate(self, preset: PresetEntry) -> None:
        if not self.save_all(show_message=False, refresh=False):
            return
        try:
            log_loss, rmse_bins = self.gateway.evaluate_preset(preset)
            showInfo(
                f"{preset.name}\n\nLog loss: {log_loss:.4f}\nRMSE(bins): {rmse_bins * 100:.2f}%",
                parent=self,
            )
        except Exception as exc:
            showWarning(f"Unable to evaluate {preset.name}:\n{exc}", parent=self)

    def open_deck_options(self, preset: PresetEntry) -> None:
        if not preset.decks:
            showWarning(f"No deck currently uses {preset.name}.", parent=self)
            return
        try:
            from aqt.deckoptions import display_options_for_deck_id

            display_options_for_deck_id(preset.decks[0].deck_id)
        except Exception as exc:
            showWarning(f"Unable to open deck options for {preset.name}:\n{exc}", parent=self)

    def _update_default_fsrs_options(self, versions: list[int]) -> None:
        current = selected_combo_data(self.default_fsrs)
        self.default_fsrs.clear()
        for version in versions:
            self.default_fsrs.addItem(fsrs_version_label(version), version)
        if current is not None:
            index = self.default_fsrs.findData(current)
            if index >= 0:
                self.default_fsrs.setCurrentIndex(index)

    def _set_default_fsrs_visible(self, visible: bool) -> None:
        self.default_fsrs_label.setVisible(visible)
        self.default_fsrs.setVisible(visible)
        self.apply_default_fsrs_button.setVisible(visible)


def retention_spin(value: float, minimum: float) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setDecimals(2)
    spin.setRange(minimum, 0.99)
    spin.setSingleStep(0.01)
    spin.setValue(value)
    return spin


def fsrs_version_combo(versions: tuple[int, ...], current_version: int | None) -> QComboBox:
    combo = QComboBox()
    for version in versions:
        combo.addItem(fsrs_version_label(version), version)
    if current_version is not None:
        index = combo.findData(current_version)
        if index >= 0:
            combo.setCurrentIndex(index)
    return combo


def selected_combo_data(combo: QComboBox) -> int | None:
    value = combo.currentData()
    return int(value) if value is not None else None


def checkbox(checked: bool) -> QCheckBox:
    widget = QCheckBox()
    widget.setChecked(checked)
    return widget


def params_line(value: str) -> QLineEdit:
    widget = QLineEdit(value)
    widget.setReadOnly(True)
    widget.setMinimumWidth(260)
    widget.setToolTip(value)
    return widget


def center_widget(child: QWidget) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addStretch()
    layout.addWidget(child)
    layout.addStretch()
    return container


def normalize_sort_value(value: Any) -> tuple[int, Any]:
    if value is None:
        return (0, "")
    if isinstance(value, bool):
        return (1, int(value))
    if isinstance(value, (int, float)):
        return (2, float(value))
    if isinstance(value, tuple):
        return (3, value)
    return (4, str(value).casefold())
