"""Config for API key and model. Config file only unless use_env_vars is set there."""

import os
from pathlib import Path


def _parse_bool(v: str) -> bool:
    return v.strip().lower() in ("true", "1", "yes", "on")


def get_config() -> dict:
    """Load config from file. Use env vars only if config has use_env_vars=true."""
    config = {
        "openai_api_key": "",
        "openai_model": "gpt-4o-mini",
        "openai_max_tokens": 200,
        "use_env_vars": False,
    }
    config_paths = [
        Path.home() / ".xforce_config",
        Path.cwd() / ".xforce",
    ]
    for p in config_paths:
        if p.exists() and p.is_file():
            try:
                with open(p) as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip().lower(), v.strip()
                            if k == "openai_api_key":
                                config["openai_api_key"] = v
                            elif k == "openai_model":
                                config["openai_model"] = v
                            elif k == "openai_max_tokens":
                                try:
                                    config["openai_max_tokens"] = int(v)
                                except ValueError:
                                    pass
                            elif k == "use_env_vars":
                                config["use_env_vars"] = _parse_bool(v)
            except OSError:
                pass
            break

    # Use env only if the user allowed it in config
    if config.get("use_env_vars"):
        if os.environ.get("OPENAI_API_KEY"):
            config["openai_api_key"] = os.environ.get("OPENAI_API_KEY", "").strip()
        if os.environ.get("OPENAI_MODEL"):
            config["openai_model"] = os.environ.get("OPENAI_MODEL", "").strip()

    return config
