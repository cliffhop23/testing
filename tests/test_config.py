from pathlib import Path

from kalshi_bot.config import DEMO_REST_URL, PRODUCTION_REST_URL, load_settings


def test_load_settings_defaults_to_demo_and_dry_run(tmp_path, monkeypatch):
    monkeypatch.delenv("KALSHI_ENV", raising=False)
    monkeypatch.delenv("KALSHI_API_KEY_ID", raising=False)
    settings = load_settings(env_file=tmp_path / "missing.env")

    assert settings.base_url == DEMO_REST_URL
    assert settings.dry_run is True
    assert settings.has_credentials is False


def test_load_settings_supports_production(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KALSHI_ENV=production\n"
        "KALSHI_API_KEY_ID=abc\n"
        "KALSHI_PRIVATE_KEY_PATH=~/kalshi.key\n"
        "KALSHI_DRY_RUN=false\n"
    )

    settings = load_settings(env_file=env_file)

    assert settings.base_url == PRODUCTION_REST_URL
    assert settings.api_key_id == "abc"
    assert settings.private_key_path == Path("~/kalshi.key").expanduser()
    assert settings.dry_run is False
