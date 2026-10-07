from app.config import get_settings


def test_settings_defaults():
    settings = get_settings()
    assert settings.database_url == "sqlite:///./certgen.db"
    assert settings.storage_dir == "./storage"
    assert settings.max_recipients_per_job == 1000
