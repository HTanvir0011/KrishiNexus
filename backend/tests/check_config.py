"""Self-check for config.get_settings: production refuses the public development signing key and allows no CORS
origins unless they are listed; development keeps working with no settings at all.
Run from backend/:  .venv/Scripts/python -m tests.check_config"""

import os

import config

KEYS = ("KNX_ENV", "KNX_RECEIPT_SIGNING_KEY", "KNX_CORS_ORIGINS")
saved = {key: os.environ.pop(key, None) for key in KEYS}


def settings(**env: str) -> config.Settings:
    for key in KEYS:
        os.environ.pop(key, None)
    os.environ.update(env)
    config.get_settings.cache_clear()
    return config.get_settings()


def refused(**env: str) -> bool:
    try:
        settings(**env)
    except RuntimeError:
        return True
    return False


try:
    dev = settings()
    assert dev.receipt_signing_key == config.DEV_SIGNING_KEY and dev.cors_origins == ["*"], dev
    assert refused(KNX_ENV="production")
    assert refused(KNX_ENV="production", KNX_RECEIPT_SIGNING_KEY=config.DEV_SIGNING_KEY)
    prod = settings(KNX_ENV="production", KNX_RECEIPT_SIGNING_KEY="a" * 64)
    assert prod.receipt_signing_key == "a" * 64 and prod.cors_origins == [], prod
    listed = settings(KNX_ENV="production", KNX_RECEIPT_SIGNING_KEY="a" * 64, KNX_CORS_ORIGINS="https://a.org, https://b.org")
    assert listed.cors_origins == ["https://a.org", "https://b.org"], listed
finally:
    for key, value in saved.items():
        os.environ.pop(key, None)
        if value is not None:
            os.environ[key] = value
    config.get_settings.cache_clear()
print("config: all checks passed")
