"""Helpers shared by several tabs."""

from __future__ import annotations

from PyQt6.QtWidgets import QComboBox

from workmods.config import WorkmodsConfig
from workmods.models import normalize_game_id
from workmods.registry import ALL_GAMES, Registry, merge_games


def populate_game_filter(
    combo: QComboBox,
    config: WorkmodsConfig,
    registry: Registry | None,
    all_label: str = "ALL GAMES",
) -> None:
    """Fill a game combo box, preserving the current selection when possible."""
    # First population must show every game; later refreshes keep what the user
    # picked (a newly added game or an active-game switch should not reset it).
    previous = combo.currentData() if combo.count() else ALL_GAMES
    games = merge_games(config.games, registry.games if registry else [])

    combo.blockSignals(True)
    combo.clear()
    combo.addItem(all_label, ALL_GAMES)
    for game in games:
        combo.addItem(game.display_name, game.id)

    target = previous if combo.findData(previous) >= 0 else ALL_GAMES
    combo.setCurrentIndex(max(combo.findData(target), 0))
    combo.blockSignals(False)


def selected_game_id(combo: QComboBox) -> str:
    data = combo.currentData()
    return normalize_game_id(data) if data else ALL_GAMES


__all__ = ["populate_game_filter", "selected_game_id"]
