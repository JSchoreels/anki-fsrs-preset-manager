from __future__ import annotations

try:
    from .fsrs_preset_manager.addon import setup

    setup()
except Exception:
    import logging

    logging.getLogger(__name__).exception("failed to initialize FSRS Preset Manager")
