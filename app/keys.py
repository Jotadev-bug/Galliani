"""Provider key storage for the desktop app: the OS credential store, never a plaintext file.

On Windows this is Credential Manager, on macOS the Keychain, on Linux the Secret Service.
Only used in desktop mode: a shared server must never keep one user's key for everyone.
"""

from __future__ import annotations

SERVICE = "galliani"
LEGACY_SERVICES = ("ai-model-router",)  # read-only, so keys saved before the rename keep working

# provider id used by the API/UI -> environment-variable name used by the registry
PROVIDERS = {
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}
OPENROUTER = PROVIDERS["openrouter"]


def _keyring():
    try:
        import keyring
    except ImportError:  # desktop extra not installed
        return None
    return keyring


def available() -> bool:
    return _keyring() is not None


def get(name: str = OPENROUTER) -> str | None:
    kr = _keyring()
    if kr is None:
        return None
    for service in (SERVICE, *LEGACY_SERVICES):
        try:
            value = kr.get_password(service, name)
        except Exception:  # a locked or broken keyring must not take the app down
            return None
        if value:
            return value
    return None


def save(value: str, name: str = OPENROUTER) -> None:
    kr = _keyring()
    if kr is None:
        raise RuntimeError("No OS credential store available (install the 'desktop' extra).")
    kr.set_password(SERVICE, name, value)


def delete(name: str = OPENROUTER) -> None:
    kr = _keyring()
    if kr is None:
        return
    for service in (SERVICE, *LEGACY_SERVICES):
        try:
            kr.delete_password(service, name)
        except Exception:  # already absent
            pass
