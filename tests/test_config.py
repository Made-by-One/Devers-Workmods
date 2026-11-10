from workmods.config import WorkmodsConfig, default_mods_dir
from workmods.models import DEFAULT_GAME_ID, Game


def test_defaults_have_one_profile():
    config = WorkmodsConfig()
    assert [game.id for game in config.games] == [DEFAULT_GAME_ID]
    assert config.install_dir_for(DEFAULT_GAME_ID).name == "DeversMods"


def test_legacy_config_migration_keeps_install_dir():
    config = WorkmodsConfig.from_dict(
        {"install_dir": "/games/mods", "language": "ru", "github_token": "t"}
    )
    assert config.language == "ru"
    assert config.github_token == "t"
    assert config.install_dir_for(DEFAULT_GAME_ID).as_posix() == "/games/mods"


def test_game_profiles_get_their_own_install_dirs():
    config = WorkmodsConfig()
    game = config.add_game(Game("space-rangers", "Space Rangers", "/games/sr/mods"))

    assert config.install_dir_for("space-rangers").as_posix() == "/games/sr/mods"
    assert config.install_dir_for(DEFAULT_GAME_ID).name == "DeversMods"
    assert game.install_dir == "/games/sr/mods"
    assert config.game_name("space-rangers") == "Space Rangers (space-rangers)"


def test_missing_profile_falls_back_to_default_layout():
    config = WorkmodsConfig()
    assert config.install_dir_for("brand-new").as_posix() == default_mods_dir("brand-new")


def test_ensure_game_creates_profile():
    config = WorkmodsConfig()
    game = config.ensure_game("Game-A")
    assert game.id == "game-a"
    assert config.game("game-a") is game
    assert config.ensure_game("game-a") is game


def test_remove_game_keeps_default_and_resets_active():
    config = WorkmodsConfig()
    config.add_game(Game("other", "Other"))
    config.active_game_id = "other"

    assert config.remove_game(DEFAULT_GAME_ID) is False
    assert config.remove_game("other") is True
    assert config.active_game_id == DEFAULT_GAME_ID
    assert config.game("other") is None


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    config = WorkmodsConfig(language="ru")
    config.add_game(Game("game-a", "Game A", str(tmp_path / "mods")))
    config.active_game_id = "game-a"
    config.save(path)

    restored = WorkmodsConfig.load(path)
    assert restored.language == "ru"
    assert restored.active_game_id == "game-a"
    assert restored.install_dir_for("game-a") == tmp_path / "mods"
    assert restored.to_dict()["games"]
