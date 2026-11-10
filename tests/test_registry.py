from workmods.models import DEFAULT_GAME_ID, Game, Mod
from workmods.registry import Registry, merge_games, mod_matches


def test_legacy_registry_payload_is_migrated():
    registry = Registry.from_payload(
        {
            "mods": [
                {"id": "a1", "name": "Old Mod", "version": "1.0"},
                {"id": "b2", "game_id": "space-rangers", "name": "New Mod"},
            ]
        }
    )

    assert registry.schema_version == 1
    by_id = registry.mods_by_id()
    assert by_id["a1"].game_id == DEFAULT_GAME_ID
    assert by_id["b2"].game_id == "space-rangers"
    # Games referenced only by mods still become selectable filters.
    assert {game.id for game in registry.games} == {DEFAULT_GAME_ID, "space-rangers"}


def test_game_and_query_filtering():
    registry = Registry.from_payload(
        {
            "schema_version": 2,
            "mods": [
                {"id": "1", "game_id": "game-a", "name": "Neon UI", "tags": ["ui"]},
                {"id": "2", "game_id": "game-b", "name": "Neon Weapons"},
                {"id": "3", "game_id": "game-a", "name": "Quiet Pack", "author": "someone"},
            ],
        }
    )

    assert [m.id for m in registry.filter(game_id="game-a")] == ["1", "3"]
    assert [m.id for m in registry.filter(game_id="game-b")] == ["2"]
    assert [m.id for m in registry.filter(game_id="game-a", query="neon")] == ["1"]
    assert [m.id for m in registry.filter(query="neon weapons")] == ["2"]
    # No game filter means every mod.
    assert len(registry.filter(game_id="")) == 3


def test_game_filter_can_include_unassigned_legacy_mods():
    legacy = Mod(id="old", name="Legacy")
    assert not mod_matches(legacy, "game-a")
    assert mod_matches(legacy, "game-a", include_unassigned=True)
    assert mod_matches(legacy, None)


def test_unknown_mod_fields_are_ignored():
    mod = Mod.from_dict({"id": "x", "game_id": "game-a", "name": "X", "vendor_field": 1})
    assert mod.to_dict()["id"] == "x"
    assert "vendor_field" not in mod.to_dict()


def test_mod_normalizes_game_id_and_tags():
    mod = Mod(id="x", game_id=" My Game!! ", tags="ui, audio")
    assert mod.game_id == "my-game"
    assert mod.tags == ["ui", "audio"]


def test_merge_games_prefers_local_names_and_sorts():
    configured = [Game("game-a", "Local A")]
    remote = [Game("game-a", "Registry A"), Game("game-b", "Game B")]

    merged = merge_games(configured, remote)

    assert [game.id for game in merged] == ["game-b", "game-a"]
    assert merged[1].name == "Local A"
