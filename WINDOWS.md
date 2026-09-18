# IntelliMap setup on Windows

Step-by-step for a clean Windows 10/11 machine. Product overview: [README.md](README.md). Operator notes: [RUNBOOK.md](RUNBOOK.md).

## 1. Install tools

Install these **before** cloning. Restart the terminal (or sign out) after each installer so `PATH` updates.

### Git

1. Download: https://git-scm.com/download/win  
2. Run the installer. Keep the default editor unless you prefer something else.  
3. Choose **Git from the command line and also from 3rd-party software**.

Check in **Command Prompt**:

```bat
git --version
```

### Python 3.11–3.14

1. Download: https://www.python.org/downloads/windows/  
2. Run the installer.  
3. Tick **Add python.exe to PATH**.  
4. Choose **Install Now**.

Check:

```bat
py -3 --version
python --version
```

`start.bat` uses **`python` on PATH** (then `py -3` if `python` is missing). It does **not** create a venv. Python **3.11–3.14** works (including 3.14.3).

### Node.js 18 or newer (20 LTS is fine)

1. Download the **LTS** Windows Installer (.msi): https://nodejs.org/  
2. Next through the wizard. Keep **npm package manager** selected.

Check:

```bat
node --version
npm --version
```

## 2. Get the code

Command Prompt:

```bat
git clone https://github.com/AkashChikane/intellimap.git
cd intellimap
```

Or download the ZIP from GitHub → **Code → Download ZIP**, extract it, then `cd` into the folder.

## 3. Environment file

```bat
copy .env.example .env
```

Open `.env` in Notepad and fill the keys you have (Gemini and/or VW LLMaaS). Empty values are fine for a deterministic demo without AI.

Do **not** commit `.env`.

## 4. Start the app (two windows)

**Window 1 — API** (keep this open):

```bat
cd intellimap
start.bat
```

The first run installs Python packages into the interpreter on PATH (no venv) and generates the sample workbook if it is missing. Wait until you see:

```
IntelliMap API - http://127.0.0.1:8000
```

**Window 2 — UI**:

```bat
cd intellimap
start-frontend.bat
```

The first run runs `npm install` inside `frontend\`. When the compile finishes, open:

http://localhost:3000

If a browser does not open, paste that URL yourself.

## 5. Smoke checks

- Header pill should read **API ready**.  
- Click **Load sample landscape**.  
- Optional LLM test (from the repo root, same `python` as `start.bat`):

```bat
python backend\test_llm.py
```

API docs: http://127.0.0.1:8000/docs  
Health: http://127.0.0.1:8000/api/health

## 6. Stop

In each window: `Ctrl+C`. Confirm with `Y` if Windows asks.

To free a stuck port:

```bat
netstat -ano | findstr :8000
taskkill /PID <pid> /F
netstat -ano | findstr :3000
taskkill /PID <pid> /F
```

## PowerShell notes

Scripts are `.bat` files. In PowerShell still run:

```powershell
.\start.bat
.\start-frontend.bat
```

If `npm` scripts are blocked, you do **not** need to change Execution Policy for these `.bat` files. Only if you later run `.ps1` scripts:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Typical Windows problems

| What you see | Fix |
| --- | --- |
| `'python' is not recognized` | Reinstall Python 3.11–3.14 from python.org with **Add to PATH**, then a **new** Command Prompt. `'py' is not recognized` is fine if `python --version` works |
| `'node' is not recognized` | Reinstall Node LTS, new Command Prompt |
| `npm` ENOENT at repo root | Always use `start-frontend.bat` (it `cd`s into `frontend`) |
| Windows Defender SmartScreen on `start.bat` | More info → Run anyway (you built/cloned this repo) |
| Port 3000 or 8000 already in use | Kill the PID with `taskkill` above, or close the old window |
| API pill **offline** | Window 1 must be running first; check http://127.0.0.1:8000/api/health |
| `error while generating package metadata` during pip | Old pins had no 3.14 wheels. `git pull`, then `rmdir /s /q backend\.venv` and run `start.bat` again |
| venv / `activate.bat` fails | Expected with the old script. Current `start.bat` ignores `backend\.venv` and calls `python` on PATH |
| `Microsoft Visual C++` / Rust errors on pip | `git pull` for 3.14-compatible pins, then retry `start.bat` |

## Screenshots for the README

After the API and UI are running, capture the gallery used in README.md:

```bat
capture-screenshots.bat
```

That writes PNGs to `docs\screenshots\` and a paste-ready block in `docs\screenshots\README-SNIPPET.md`. The script does **not** edit README.md.

Requires Node on PATH. First run installs Playwright Chromium under `scripts\`.

## Layout reminder

```
intellimap\
  start.bat              API
  start-frontend.bat     UI
  .env                   your secrets (local only)
  backend\               FastAPI
  frontend\              React
  data\                  sample .xlsx
```
