"""LLM integration via Ollama for cortex."""

from pathlib import Path

import yaml

# Load prompts from YAML
_PROMPTS_PATH = Path(__file__).parent / "prompts.yaml"


def load_prompts() -> dict:
    """Load prompt templates from prompts.yaml."""
    with open(_PROMPTS_PATH) as f:
        return yaml.safe_load(f)


def query_ollama(prompt: str, model: str = "qwen2.5:0.5b") -> tuple[str, str | None]:
    """Query local Ollama instance.

    Returns (response, error). Error is None on success.
    """
    import requests

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("response", ""), None
    except requests.exceptions.ConnectionError:
        return "", "Ollama not running. Start with: ollama serve"
    except requests.exceptions.Timeout:
        return "", "Ollama request timed out"
    except Exception as e:
        error_msg = str(e)
        if "model" in error_msg.lower() and "not found" in error_msg.lower():
            return "", f"Model not found. Install with: ollama pull {model}"
        return "", f"Ollama error: {error_msg}"


def refine_project(content: str, task_count: int, model: str = "qwen2.5:0.5b") -> tuple[str, str, str | None]:
    """Analyze a project and return improvement suggestions.

    Returns (prompt, response, error). Error is None on success.
    """
    prompts = load_prompts()
    prompt = prompts["refine_project"].format(content=content, task_count=task_count)
    response, error = query_ollama(prompt, model)
    return prompt, response, error
