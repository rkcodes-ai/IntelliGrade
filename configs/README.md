# Configs

Non-secret, environment-specific configuration shared by tooling outside the app
runtimes themselves (e.g. monitoring agent configs, nginx configs for future
reverse-proxy deployment). Runtime app configuration lives in:

- `backend/app/core/config.py` (+ `backend/.env.example`)
- `frontend/src/config/` (+ `frontend/.env.example`)

Empty in Module 01 — populated as deployment targets are added.
