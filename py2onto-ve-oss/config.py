"""Load unified config from config.json with fallback to environment variables.

Usage::

    from config import load_config, get_llm_config

    cfg = load_config()           # full config dict (empty if no config.json)
    llm_cfg = get_llm_config("deepseek")  # api_key, model, base_url for a provider
"""

import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

# Environment variable fallback map per provider
_ENV_KEY_MAP = {
    "deepseek": "DEEPSEEK_API_KEY",
    "chatglm": "CHATGLM_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "ollama": "OLLAMA_API_KEY",
}


def load_config() -> dict:
    """Load config.json as a dict. Returns empty dict if the file does not exist."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def get_llm_config(provider: str) -> dict:
    """Get LLM configuration for *provider*.

    Looks up ``config.json`` → ``llm.<provider>`` first, then falls back to the
    corresponding environment variable for the API key.

    Returns a dict with keys ``api_key``, ``model``, ``base_url``.
    """
    cfg = load_config()
    llm = cfg.get("llm", {})
    prov = llm.get(provider, {})

    api_key = prov.get("api_key", "") or os.environ.get(
        _ENV_KEY_MAP.get(provider, ""), ""
    )
    model = prov.get("model", "")
    base_url = prov.get("base_url", "")

    # Ollama has a standard default endpoint
    if provider == "ollama" and not base_url:
        base_url = "http://localhost:11434/v1"

    return {"api_key": api_key, "model": model, "base_url": base_url}


def get_system_prompt() -> str:
    """Get the LLM system prompt from config.json.

    Returns the configured prompt, or empty string if not set.
    """
    cfg = load_config()
    return cfg.get("system_prompt", "")


def save_system_prompt(prompt: str) -> None:
    """Save the LLM system prompt to config.json.

    Preserves all other config values.
    """
    cfg = load_config()
    cfg["system_prompt"] = prompt
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_task_prompt() -> str:
    """Get the LLM task prompt from config.json.

    Returns the configured task prompt, or empty string if not set.
    """
    cfg = load_config()
    return cfg.get("task_prompt", "")


def save_task_prompt(prompt: str) -> None:
    """Save the LLM task prompt to config.json.

    Preserves all other config values.
    """
    cfg = load_config()
    cfg["task_prompt"] = prompt
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_portal_config() -> dict:
    """Get MedPortal / BioPortal configuration.

    Returns a dict with keys ``medportal_url``, ``medportal_api_key``,
    ``bioportal_url``, ``bioportal_api_key``.
    """
    cfg = load_config()
    mp = cfg.get("medportal", {})
    bp = cfg.get("bioportal", {})

    return {
        "medportal_url": mp.get("url", "http://medportal.bmicc.cn:8080"),
        "medportal_api_key": mp.get("api_key", ""),
        "bioportal_url": bp.get("url", "http://data.bioontology.org"),
        "bioportal_api_key": bp.get("api_key", ""),
    }
