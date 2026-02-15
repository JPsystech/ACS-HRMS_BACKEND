# Quick Start Guide

**ACS HRMS Backend - Quick Reference**

## Common Commands

All commands must be run from the `hrms-backend` directory (project root).

### Start Development Server

```bash
cd hrms-backend
python -m uvicorn app.main:app --reload
```

Server will be available at: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/v1/health`

### Run Database Migrations

```bash
cd hrms-backend
python -m alembic upgrade head
```

**Note:** If you see `No config file 'alembic.ini' found`, you're in the wrong directory. Make sure you're in `hrms-backend`.

### Run Tests

```bash
cd hrms-backend
pytest
```

Run specific test:
```bash
cd hrms-backend
pytest app/tests/test_health.py -v
```

**Note:** If you see `ModuleNotFoundError: No module named 'app'`, you're in the wrong directory. Make sure you're in `hrms-backend`.

### Check Project Structure

The project root (`hrms-backend`) should contain:
- `app/` folder (with `main.py`, `core/`, `api/`, etc.)
- `alembic/` folder
- `alembic.ini` file
- `requirements.txt`
- `README.md`

## Troubleshooting

### "No module named 'app'"
- **Cause:** Running command from wrong directory
- **Fix:** `cd hrms-backend` first, then run your command

### "No config file 'alembic.ini' found"
- **Cause:** Running Alembic from wrong directory
- **Fix:** `cd hrms-backend` first, then run `alembic upgrade head`

### "ImportError" or "ModuleNotFoundError" in tests
- **Cause:** Running pytest from wrong directory
- **Fix:** `cd hrms-backend` first, then run `pytest`

## Directory Structure

```
hrms-backend/          ← Always run commands from here
├── app/
│   ├── main.py
│   ├── core/
│   ├── api/
│   ├── models/
│   └── tests/
├── alembic/
│   └── versions/
├── alembic.ini        ← Alembic config (must be in project root)
├── requirements.txt
└── README.md
```

---

**Developed & Designed by JPSystech**
