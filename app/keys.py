"""Provider key storage for the desktop app: the OS credential store, never a plaintext file.

On Windows this is Credential Manager, on macOS the Keychain, on Linux the Secret Service.
Only used in desktop mode: a shared server must never keep one user's key for everyone.
"""

from __future__ import annotations

SERVICE = "ai-model-router"
OPENROUTER = "OPENROUTER_API_KEY"


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
    try:
        return kr.get_password(SERVICE, name) or None
    except Exception:  # a locked or broken keyring must not take the app down
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
    try:
        kr.delete_password(SERVICE, name)
    except Exception:  # already absent
        pass
