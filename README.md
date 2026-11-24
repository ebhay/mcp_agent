# TrainMate Mail and Agent

A mail system and AI agent for TrainMate coaches and admins, built from:

- `backend/`: FastAPI API for login, mail, and the agent (chat and mail workflow).
- `frontend-mcp/`: React (Vite) UI for mail and the agent.
- `TrainMate/`: the TrainMate Java backend and Angular frontend (see `TrainMate/README.md`).

## Prerequisites

- Python 3.10 or newer
- Node.js 20.19 or newer (22.12 or newer recommended)
- Database: a local SQLite file (`backend/app.db`, created automatically), or your local MySQL 8 server if you want to manage the data in MySQL Workbench (see below).
- An OpenAI API key (ChatGPT API). Create one at platform.openai.com.

## Quick start

Do this once, then start the backend and frontend every time you work on the project.

**Windows (PowerShell)**

```powershell
# Backend: one-time setup
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then fill in .env (see section 1)

# Backend: start (every time)
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

```powershell
# Frontend: one-time setup, then start (every time)
cd frontend-mcp
npm install
npm run dev
```

**macOS / Linux (bash)**

```bash
# Backend: one-time setup
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in .env (see section 1)

# Backend: start (every time)
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

```bash
# Frontend: one-time setup, then start (every time)
cd frontend-mcp && npm install && npm run dev
```

Open `http://localhost:5173`. The backend health check is `http://localhost:8000/api/health`.

The sections below explain each step and the troubleshooting.

## 1. Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
```

Edit `backend/.env`:

| Variable | What to set |
| --- | --- |
| `DATABASE_URL` | `sqlite:///./app.db` (default, local file). For local MySQL 8 (Workbench): `mysql+pymysql://user:password@localhost:3306/mailagent`. For PostgreSQL: `postgresql+psycopg://user:password@localhost:5432/mailagent` |
| `OPENAI_API_KEY` | Your OpenAI (ChatGPT API) key |
| `OPENAI_BASE_URL` | Leave blank for OpenAI |
| `OPENAI_MODEL` | Chat model, e.g. `gpt-4o-mini` |
| `EMBEDDING_MODEL` | Embedding model, e.g. `text-embedding-3-small` |
| `TRAINMATE_BASE_URL` | TrainMate API URL (default is the hosted instance) |
| `APP_BASE_URL` | This backend's URL (default `http://localhost:8000`) |
| `COACH_LOGIN_ID` / `COACH_PASSWORD` | Demo coach login. Must match a coach in TrainMate |
| `ADMIN_LOGIN_ID` / `ADMIN_PASSWORD` | Demo admin login. Must match an admin in TrainMate |
| `TRAINER_LOGIN_ID` / `TRAINER_PASSWORD` | Demo trainer login |

### Use MySQL Workbench (local MySQL 8)

1. Open **MySQL Workbench** and connect to your local MySQL server (usually `Local instance MySQL80`, port `3306`).
2. In a query tab, create the database (run it once):

   ```sql
   CREATE DATABASE IF NOT EXISTS mailagent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

3. In `backend/.env`, set the connection (use your own MySQL username and password):

   ```
   DATABASE_URL=mysql+pymysql://root:YOUR_MYSQL_PASSWORD@localhost:3306/mailagent
   ```

4. Start the backend. The `users`, `sessions`, and `messages` tables are created automatically and the demo users are added.
5. In Workbench, right-click **Schemas** and choose **Refresh All** to see `mailagent`. Mail is in the `messages` table.

Use a MySQL user with access to `mailagent` rather than `root` if you can. The `mailagent` database is separate from TrainMate's `trainmate` database.

Never commit `.env`. It holds secrets, and `.gitignore` already excludes it.

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Check it is running: open `http://localhost:8000/api/health`. Interactive docs are at `http://localhost:8000/docs`.

On startup the backend creates the tables and the demo users from `.env` in the database. If a password is empty, the server stops with a clear message.

### Run the mail workflow from the command line (optional)

```bash
python -m agent.run
```

This runs the coach mail workflow once and prints a JSON report. The same workflow runs from the UI with the **Mail workflow** button.

## 2. Frontend

In a second terminal:

```bash
cd frontend-mcp
npm install
npm run dev
```

Open `http://localhost:5173`.

The UI talks to `http://localhost:8000` by default. To point it elsewhere, create `frontend-mcp/.env.local` with:

```
VITE_API_URL=http://localhost:8000
```

Other scripts: `npm run build` (production build), `npm run lint`, `npm run preview`.

## 3. Using the app

1. Use the **Switch user** dropdown in the sidebar to pick a demo account (no password needed in this demo mode).
2. As **admin**, open **Mail**, click **Compose**, and send a message to a coach.
3. Switch to the **coach** account, open **Agent**, and click **Mail workflow**. The agent reads unread mail, creates batches from batch requests, and reallocates unassigned cohorts.
4. In **Agent**, you can also ask questions in chat. Destructive actions ask for confirmation first.

Batch request mails need: cohort code, required skill, number of trainees, start date, and end date. The agent asks the admin for anything missing.

## Batch request mail format

An admin sends a new batch request to a coach using **Mail → Compose → New cohort template**. The template has these lines:

| Field | Required | Format and allowed values |
| --- | --- | --- |
| Cohort Code | Yes | Unique code, up to 30 characters |
| Trainees Count | Yes | Whole number from 1 to 500 |
| Required Skill(s) | Yes | Separate multiple skills with commas |
| Service Line | No | QEA, ADM, CDE or CIS (default QEA) |
| Stream | No | Software Development, Web Development, Cloud Infrastructure or Data Engineering |
| Start Date | Yes | YYYY-MM-DD (DD-MM-YYYY also accepted) |
| End Date | Yes | YYYY-MM-DD, on or after the start date |
| Industry Vertical | No | Healthcare, Banking, Retail, Insurance or Communications |
| Training Location | No | Chennai, Pune, Bangalore, Hyderabad, Kolkata or Virtual |

The Compose screen checks these rules before sending. The coach's **Mail workflow** reads unread mail, creates the batch from a filled-in template, and replies to the admin. Mail that is not a batch request is left unread. Free-form batch requests are also accepted and read by the AI model, but they are less reliable than the template.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| "Cannot reach the backend" in the UI | Start the backend, and check `VITE_API_URL` and port 8000 |
| `Database is unavailable` (503) | Check `DATABASE_URL` in `backend/.env`. For MySQL, make sure the server is running, the `mailagent` database exists, and the username and password are right. For SQLite, the `backend` folder must be writable |
| `Access denied for user` | Wrong MySQL username or password in `DATABASE_URL` |
| `Set the ... password in backend/.env` | Fill in the password variables in `.env` and restart |
| AI provider busy or quota exceeded (429/503) | Wait a minute and retry. If it persists, check usage and billing at platform.openai.com |
| TrainMate did not respond (504) | The hosted TrainMate may be waking up; retry after a minute |
| `Coach mail account must have the coach role` | Check `COACH_LOGIN_ID` matches a coach in TrainMate |

## Security notes

- Demo login switching has no password, so it is for local demos only. Don't expose the backend to the public internet in this state.
- Rotate any API key or database password that was ever pasted into chat, logs, or a shared file.
