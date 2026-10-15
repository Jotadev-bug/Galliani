# Release Checklist

Spec 013 requires evaluation reporting to be part of every release. A release is blocked until each item below holds.

## 1. Tests

```bash
python -m pytest tests
```

All tests pass. Skips are allowed only where the platform cannot support the test (for example, symlink creation on Windows without privileges).

## 2. Evaluation gates

```bash
python -m galliani.evaluation evals/cases
```

The command exits 0, and every blocking quality gate passes:

| Gate | Threshold | Spec |
|---|---|---|
| `loop_pass_rate` | 1.0 | 013 R5 |
| `permission_bypasses` | 0 | 005, 009 |
| `hidden_reasoning_leaks` | 0 | 000 R6, 011 R5 |
| `false_done_on_negative` | 0 | 001, 007 |
| `unauthorized_memory_writes` | 0 | 010 |
| `secret_memory_persistence` | 0 | 010 |

Paste the "Quality gates" block of the report into the release entry in `CHANGELOG.md`.

## 3. Architecture boundaries

- `tests/core/test_foundation.py` passes: core modules import no provider SDK, no `app` code, and no `galliani.providers` adapter (Decisions 0009, 0012).
- Every new behavior maps to a numbered spec requirement or a recorded decision in `docs/decisions.md`.

## 4. Live smoke run (manual, costs a few cents)

Run one real objective against a disposable folder and confirm it ends `done`, asks before writing, and prints a usage line:

```bash
python -m galliani.cli "Summarize agent-loop.md in five bullets and save it as summary.md" --workspace docs --events smoke.jsonl
```

Then check `smoke.jsonl` for leaks; this must print nothing:

```bash
python -c "import re,sys; t=open('smoke.jsonl',encoding='utf-8').read(); [print(m) for m in re.findall(r'sk-[A-Za-z0-9_-]{16,}|\"(reasoning|thinking|chain_of_thought)\"\s*:', t)]"
```

Delete `docs/summary.md` and `smoke.jsonl` afterwards.

## 5. Publish

Bump `version` in `pyproject.toml`, commit, then push **only** the matching tag (`v0.1.0`, or `v0.2.0-beta.1` for a pre-release):

```bash
git tag v0.1.0
git push origin v0.1.0
```

Push the tag on its own, not with `--tags` or together with a branch, so GitHub sends the tag push event that starts the `Release` workflow. If no Release run appears under **Actions** within a minute, start it by hand: **Actions > Release > Run workflow**, leave the branch on `main`, enter the tag (for example `v0.1.0`), and click **Run workflow** (spec 016 R1).

Either way the workflow refuses a tag that is malformed, missing or does not match `pyproject.toml` (`scripts/release_tag.py`), runs the tests, builds `Galliani.exe`, and fails unless the binary's `--smoke-test` passes. Check the published release has the `.exe` and its `.sha256`. Stable releases become "latest"; pre-releases never do, so `https://github.com/Jotadev-bug/Galliani/releases/latest/download/Galliani.exe` always serves the newest stable build.

## 6. Before announcing (manual)

Spec 016 R4. Do not link the release anywhere until each step holds.

1. **Clean machine.** On a clean Windows 10 or 11 machine, or a fresh Windows Sandbox, download `Galliani.exe` from the release page. Check its SHA-256 against `Galliani.exe.sha256`:

   ```powershell
   (Get-FileHash Galliani.exe -Algorithm SHA256).Hash
   ```

   Run it past SmartScreen (**More info**, then **Run anyway**), add an OpenRouter key, send one chat message, and run one agent task in a throwaway folder. All three must work.
2. **VirusTotal.** Upload the `.exe` to [virustotal.com](https://www.virustotal.com/gui/home/upload) and keep the report link. Add it to the release notes.
3. **False positives.** If Microsoft Defender or another major engine flags the file, submit it as a false positive. Microsoft's portal is free: [microsoft.com/wdsi/filesubmission](https://www.microsoft.com/en-us/wdsi/filesubmission) (choose "Software developer"). For other engines, use their own false-positive form. Note each submission and its date in the release notes. Never tell users to turn off SmartScreen or their antivirus.

## 7. winget (manual)

Spec 016 R17. The Release workflow attaches `galliani-winget-<version>.zip` (the same files as `packaging/winget/<version>/`, with the new release's checksum). Do this after the release is published and R4 holds.

1. Unzip the manifest into `packaging/winget/<version>/` and commit it. For an older release, regenerate it with the checksum from the release's `.sha256` file:

   ```bash
   python -m scripts.winget_manifest --tag v0.1.0 --sha256 <hash> --release-date YYYY-MM-DD --out packaging/winget/0.1.0
   ```

2. Validate it:

   ```powershell
   winget validate --manifest packaging\winget\<version>
   ```

3. On a clean machine or Windows Sandbox, allow local manifests once (`winget settings --enable LocalManifestFiles`, as administrator), then install from the folder and check the command works:

   ```powershell
   winget install --manifest packaging\winget\<version>
   galliani
   ```

4. Fork `microsoft/winget-pkgs` and copy the three files to `manifests/j/Jotade/Galliani/<version>/` (the path follows the package identifier: its first letter, then each part). Open a pull request. Its automated checks download the `.exe`, compare the checksum and scan it; fix anything they report.
5. Once merged, add `winget install Jotade.Galliani` to the site's Install section (spec 016 R7.4).

The package identifier cannot change after the first merge. See spec 016 Open Question 1.

## 8. Microsoft Store (manual)

Spec 016 R18-R23. The Store build is `Galliani.msix`; the Store signs it, so it is submitted unsigned. Do this once after R4 holds for the same version.

**Once, in Partner Center** (your individual developer account is already verified):

1. **Reserve the name.** Apps and games > New product > MSIX or PWA app > reserve "Galliani".
2. **Copy the identity.** Product management > Product identity. Copy *Package/Identity/Name* and *Package/Identity/Publisher* (it looks like `CN=xxxxxxxx-xxxx-...`) into `packaging/msix/identity.json` (`identity_name`, `publisher`). They are not secret. `publisher_display_name` must equal *Package/Properties/PublisherDisplayName* (currently "Jotade"). Commit the file.

**For each release:**

1. **Build.** Pushing the tag builds `Galliani.msix` in the Release workflow once the identity is committed (a failure there never blocks the `.exe`). To build by hand: `python -m scripts.build_msix`.
2. **Test it locally first** (R22). Build a test package with a throwaway identity and certificate, trust that certificate, install the package and run it:

   ```powershell
   python -m scripts.build_msix --local-test
   # As administrator, trust the throwaway certificate (undo it afterwards, see below):
   Import-Certificate -FilePath dist\Galliani.cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople
   Add-AppxPackage dist\Galliani.msix
   ```

   Start **Galliani (local test)** from the Start menu. Check that the window opens, a key you add survives closing and reopening the app, the folder picker works, and an agent task completes. Then remove it:

   ```powershell
   Get-AppxPackage Galliani.LocalTest | Remove-AppxPackage
   # As administrator:
   Get-ChildItem Cert:\LocalMachine\TrustedPeople | Where-Object Subject -eq 'CN=Galliani Local Test' | Remove-Item
   ```

   The throwaway certificate is created for each run, deleted from the certificate store right after signing, and never committed or published. Never trust it on a machine you do not own.
3. **Create the submission.** In Partner Center, start a submission for Galliani and fill in:
   - Pricing: free.
   - Properties: category (Productivity or Developer tools), and the privacy policy URL `https://galliani.vercel.app/privacy.html`.
   - Age rating questionnaire (no user-generated content shared between users, no purchases).
   - Store listing: the description and short description from the site, at least one 1366x768 or larger screenshot of the app (take real ones), and the logo tiles from `packaging/msix/Assets/`.
   - Packages: upload `Galliani.msix` (from the release assets, or built locally with the same command).
   - Notes for certification: it is a desktop app that needs the user's own OpenRouter key; say so, and give a throwaway test key if the testers ask.
4. **Submit** for certification and watch the Partner Center dashboard. Fix whatever the report names and resubmit.
5. Once live, add the Store link to the site's Install section and the README.

Increase `version` in `pyproject.toml` for every new submission: the Store rejects a package version it has already seen.

## 9. Documentation

- `CHANGELOG.md` lists the change with its spec references.
- `docs/decisions.md` records any change to contracts, lifecycle states, or security behavior.
- Spec "Implementation Tasks" checkboxes reflect what shipped.
