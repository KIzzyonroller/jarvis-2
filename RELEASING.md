# Turning Jarvis into an installable app (and pushing updates)

You end up with a normal Windows installer, `JarvisAssistant-win-Setup.exe`. Whoever installs it gets Jarvis in
their Start menu, and every copy updates itself when you publish a new version. GitHub does the building on
its own Windows machines, so you don't need anything extra installed on your PC.

## What you need

- A GitHub account (free), with **two-factor authentication on**. Anyone who gets into this account can push
  an "update" to every installed copy, so protect it like your bank login.
- [GitHub Desktop](https://desktop.github.com) is the easiest way to upload the code.

## One-time setup

1. **Decide where releases live.** Installed copies download updates from a GitHub releases page, and that
   page has to be **public** (an app can't safely carry a password to a private one).
   - **Simple:** one public repo with the code and the releases. Your code is visible to anyone. It contains
     no keys (those stay in `.env`, which is never uploaded).
   - **Code stays private:** a private repo for the code plus a second, empty, public repo just for
     releases (e.g. `jarvis-releases`). See "Private code" below for the two extra settings.
2. **Upload the code.** In GitHub Desktop: File > Add local repository > pick the Jarvis folder > "create a
   repository" > Publish. Before you click Publish, look at the list of files and make sure **`.env` is not
   in it** (the included `.gitignore` keeps it out; check anyway).
3. **First release.** On github.com, open the repo > **Actions** > **Release** > **Run workflow**, type
   `1.0.0`, and run it. It takes about 15 to 25 minutes. When it's green, the **Releases** page has
   `JarvisAssistant-win-Setup.exe`.

## Installing it

1. Download `JarvisAssistant-win-Setup.exe` from the Releases page and run it. Until you sign your builds
   (see below), Windows shows "Windows protected your PC": click **More info** > **Run anyway**.
2. It installs into `%LOCALAPPDATA%\JarvisAssistant` (no admin needed) and starts. The first time:
   - a setup card asks for your Claude API key (and optionally Groq). It checks the key with Anthropic and
     saves it in `%LOCALAPPDATA%\JarvisData\.env`.
   - he downloads his voice (about 350 MB) in the background, using a stand-in voice until it's done.
3. Uninstall from Windows Settings > Apps like any program. Your memory, reminders and settings in
   `Documents\Jarvis` are left alone.

**Moving from the folder version:** memory, reminders, history and settings carry over automatically (they're
in `Documents\Jarvis`). Paste your keys into the setup card once. Quit the old one first; if "Start with Windows"
was on, switch it on again in the new app (it then points at the new one).

## Pushing an update

1. Change the code (or drop in a new version from me). Add a section at the top of `CHANGELOG.md` starting with
   `## <version>` and a list of what's new (I do this in every version I send). Installed copies show it on the
   update card and in the "What's new" pop-up after updating.
2. Commit and push in GitHub Desktop.
3. Actions > Release > Run workflow, with a **higher** version than last time (`1.0.1`, `1.1.0`...). Or push a
   tag: `git tag v1.0.1` then `git push origin v1.0.1`.

Every installed copy checks a few seconds after it starts and then every 6 hours. It downloads the update quietly,
then says it's ready. "Update yourself" installs it straight away (with an approval card); otherwise it installs the
next time he starts.

Rules:
- Versions only go up. A build with a lower or equal number is ignored by installed copies.
- Never change `$PackId` in `build.ps1` after the first release. Installed copies only accept updates with
  the same ID; changing it means everyone reinstalls. The visible name (`$Title`) can change any time.
- Never commit `.env` or paste tokens or keys into code, issues or chats.

## If a build fails

Open the failed run in the Actions tab. The useful parts:
- **SELFTEST FAILED** lists exactly which parts didn't make it into the package (usually a missing module).
  Send me that list.
- The **build-output** download on the run page has `warn-Jarvis.txt`, PyInstaller's list of things it
  couldn't find.

To build on your own PC instead (Python 3.12 and the .NET 8 SDK needed):
`powershell -ExecutionPolicy Bypass -File build.ps1 -Version 1.0.0 -UpdateSource https://github.com/YOU/REPO`
The installer lands in `Releases\`. Nothing is published without `-Publish`.

## Private code (optional)

1. Make a second, **public**, empty repo for releases, e.g. `YOU/jarvis-releases`.
2. Make a token that can write to it: GitHub > Settings > Developer settings > Fine-grained tokens > access to
   only that repo > Contents: Read and write.
3. In the **code** repo: Settings > Secrets and variables > Actions:
   - Secrets > New: `RELEASES_TOKEN` = the token.
   - Variables > New: `RELEASES_REPO` = `YOU/jarvis-releases`.

Do this **before** your first release. Installed copies remember where they get updates from, so switching later
means one manual reinstall.

## Signing (later, to get rid of the "Windows protected your PC" screen)

Microsoft's **Azure Artifact Signing** is available to individuals in Canada and the US for about $10 USD a
month. Setup is roughly:
1. Create an Azure account, an Artifact Signing account, and complete identity validation (takes a few days).
2. Create a certificate profile, and an app registration that's allowed to sign with it.
3. Add these secrets to the repo: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`,
   `AZURE_SIGN_ENDPOINT` (like `https://eus.codesigning.azure.net/`), `AZURE_SIGN_ACCOUNT`, `AZURE_SIGN_PROFILE`.

The workflow signs automatically once they exist. Even signed, a brand-new publisher can still get a warning
until enough people have installed it; that fades over time.

## The name

"Jarvis" and "Ultron" are Marvel characters. That's fine on your own PC and for a few friends, but if this ever
goes public (a website, strangers downloading it), rename the app and its personas first. Only `$Title`,
the window title and the persona text need to change; `$PackId` stays as it is.
