# Galliani 0.2.0

Galliani 0.2.0 makes the agent safer on your computer and handles a missing or broken Microsoft Edge WebView2 with a clear message instead of an empty window.

**Breaking: API clients must send `X-Requested-With` or `X-App-Token`.** If you call Galliani's local `/api` from your own scripts or tools, every state-changing (non-GET) request now needs one of those headers, plus a same-origin `Origin`. The server also only answers the host names `127.0.0.1`, `localhost` and `[::1]`. The Galliani app itself is not affected.

## What's new

- **Safer file access.** The agent can no longer reach protected files (`.env`, keys, `.git/`) through Windows tricks such as case changes, trailing dots, alternate data streams, device names, links, junctions or short names. Accept-edits mode cannot plant a git hook.
- **A web page cannot approve agent actions.** The local server checks the request headers and the `Host` name, which closes cross-site and DNS-rebinding attacks on the local API.
- **Better secret masking.** More token formats (GitHub, Google, Slack, GitLab, Stripe) are masked in logs and refused by memory, and ordinary words are no longer masked by mistake. `desktop.log` can no longer hold a secret.
- **WebView2 handling.** If Microsoft Edge WebView2 is missing, Galliani shows a message and offers Microsoft's WebView2 page, which opens in your browser only if you choose Yes. If WebView2 is installed but fails to start, you get a message instead of an empty window. Galliani never downloads or runs an installer.
- **Known limitation.** Hard links to protected files are not blocked yet (SEC-9). This is accepted residual risk for this release and is tracked in `docs/security.md`.

See `CHANGELOG.md` for the full list.

## First launch: the "unknown publisher" warning

`Galliani.exe` is **not code-signed yet**. A code-signing certificate is planned, but it is not available for this release. Because of that, Windows SmartScreen will warn "Windows protected your PC" with "Unknown publisher" the first time you run it. That warning means Windows does not recognize the publisher; it does not mean a problem was found in the file.

To run it:

1. Click **More info**.
2. Click **Run anyway**.

You only need to do this once per downloaded copy. Please do not turn off SmartScreen or your antivirus for it. If you want more certainty, check the checksum first (below), and remember the full source code is public under the GNU AGPL-3.0.

## Check the download (SHA-256)

Each release has a `Galliani.exe.sha256` file. Compare it with the hash of your download in PowerShell, from the folder that holds `Galliani.exe`:

```powershell
(Get-FileHash .\Galliani.exe -Algorithm SHA256).Hash
```

The two values must be the same (letter case does not matter). If they differ, delete the file and download it again from the GitHub Releases page.

## Windows 10 and WebView2

Galliani's window uses Microsoft Edge WebView2. Windows 11 and up-to-date Windows 10 machines normally have it. If yours does not, Galliani tells you and offers Microsoft's page (`https://developer.microsoft.com/microsoft-edge/webview2/`); install the "Evergreen" runtime from there and start Galliani again. The app exits with code 3 in that case, and a window that fails to start exits with code 4. One line explaining why is written to `%LOCALAPPDATA%\Galliani\desktop.log`, on your computer only. Nothing is sent anywhere.

## Install

- Download `Galliani.exe` from this page (Windows 10/11). You need your own [OpenRouter](https://openrouter.ai/keys) key. It is stored in your OS credential store.
- winget: the manifest for this version is prepared; `winget install Jotade.Galliani` works only after it is accepted into the community repository. Until then, use the download above.

## Checks

<!-- Fill in before publishing, from docs/release-checklist.md. -->
- VirusTotal report: <link>
- Clean-machine test: Windows 10 without the WebView2 runtime passed on 2026-10-16 (tested by the maintainer; Windows build not recorded). Other machines: <result>
- False-positive submissions, if any: <list with dates>
