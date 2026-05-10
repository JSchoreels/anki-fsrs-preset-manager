from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from aqt import mw
from aqt.qt import QAction

from .dialog import FsrsPresetManagerDialog

LOGGER_NAME = "fsrs_preset_manager"
LOG_FILE_NAME = "fsrs_preset_manager.log"


def setup() -> None:
    _configure_logging()
    action = QAction("FSRS Preset Manager", mw)
    action.triggered.connect(open_dialog)
    mw.form.menuTools.addAction(action)


def open_dialog() -> None:
    logging.getLogger(LOGGER_NAME).info("opening FSRS Preset Manager")
    dialog = FsrsPresetManagerDialog(mw)
    dialog.exec()


def _configure_logging() -> None:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return
    try:
        path = _profile_file(LOG_FILE_NAME)
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    except Exception:
        logger.addHandler(logging.NullHandler())


def _profile_file(file_name: str) -> Path:
    profile_folder_getter = getattr(getattr(mw, "pm", None), "profileFolder", None)
    if callable(profile_folder_getter):
        folder = profile_folder_getter()
        if isinstance(folder, str) and folder:
            return Path(folder) / file_name
    return Path(__file__).resolve().parent.parent / file_name
