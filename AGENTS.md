# Repository Guidelines

## Project Structure & Module Organization
`main.py` is the FastAPI entrypoint, dashboard server, and background trading loop. Core trading logic lives in `core/` (`strategy.py`, `bithumb_client.py`, `discord_notifier.py`). Data models are defined in `models.py`, and environment loading is in `config.py`.

UI files are split between `templates/` for Jinja HTML and `static/` for CSS, icons, the PWA manifest, and service worker assets. Operational notes live in `docs/`. Ad hoc verification scripts are currently kept in `scratch/`.

## Build, Test, and Development Commands
Set up and run locally:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.template .env
python main.py
```

`python main.py` starts the app on `http://localhost:8000` with `uvicorn` reload enabled from the `__main__` block. Use `docker build -t bitrade .` to build the container image defined by `Dockerfile`.

Manual checks:

```bash
python scratch/test_security.py
python scratch/test_bithumb_auth.py
```

Run these only against a local app instance with valid `.env` settings.

## Coding Style & Naming Conventions
Follow the existing Python style: 4-space indentation, `snake_case` for functions and variables, `PascalCase` for classes and Pydantic models, and clear module names such as `discord_notifier.py`. Keep FastAPI route handlers and trading helpers small enough to review independently. Prefer explicit imports and short doc-comments only where behavior is not obvious.

No formatter or linter is checked in. Match the surrounding style and keep changes minimal and consistent.

## Testing Guidelines
This repository does not yet have a formal `pytest` suite. Add focused script-based checks in `scratch/` for operational cases, and prefer names like `test_<feature>.py`. For logic-heavy changes, include a reproducible manual verification path in the PR description.

## Commit & Pull Request Guidelines
Recent history uses Conventional Commit prefixes such as `feat:`, `fix:`, and `docs:`. Keep subjects short and imperative, for example `fix: convert Discord timestamps to KST`.

PRs should include:
- A short summary of the behavior change
- Any required `.env` or deployment updates
- Screenshots for dashboard/UI changes in `templates/` or `static/`
- Manual test steps and results

## Security & Configuration Tips
Keep secrets only in `.env`; never commit exchange keys, webhook URLs, or production credentials. Treat `btrd.pem` and any deployment scripts as sensitive operational material, and document config changes in `docs/` when they affect setup or hosting.
