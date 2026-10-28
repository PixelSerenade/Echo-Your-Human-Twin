# Echo-Your HumanTwin AI

> **Project status: In progress.** Echo is actively being developed and deployed; features and behavior may continue to change.

## Persona-aware memory

The backend registry in `backend/memory_registry.py` defines persona presets, category permissions, UI labels, prompt examples, and simulator dimensions. Existing timetable, deadline, focus-log, and preference tables remain in place and are exposed through generic memory categories, so existing rows and permission settings remain available. Startup adds the `users.persona` column with a `student` default and creates the new `goals` table without deleting existing data.

To add the synthetic working-professional and freelancer demo accounts to PostgreSQL, run `python -m backend.scripts.seed_persona_demos` from the repository root. The script is safe to rerun; existing demo accounts are left alone.

> **An intelligent digital twin that learns from permitted data, simulates "what-if" life scenarios, recommends balanced decisions, and evolves dynamically from user feedback.**

HumanTwin AI models a person through three internal thinking styles ("twins"):
* **Rational Twin**: Time, deadlines, workload, risk, practicality, and efficiency.
* **Emotional Twin**: Stress, happiness, motivation, comfort, peace of mind, and burnout prevention.
* **Ambitious Twin**: Career goals, professional differentiation, skill mastery, and long-term opportunities.

---

##  System Architecture & Tech Stack

```
                     ┌───────────────────────────────────────────────┐
                     │          React + Vite + Tailwind UI           │
                     │  (Control Room, Recharts, Interactive Cards)  │
                     └───────────────────────┬───────────────────────┘
                                             │ REST API
                                             ▼
                     ┌───────────────────────────────────────────────┐
                     │             FastAPI Backend (Async)           │
                     │                                               │
                     │  ┌─────────────────────────────────────────┐  │
                     │  │   Single Gateway Data Access Function   │  │
                     │  │   (Strict Permission Filter + Audit Log)│  │
                     │  └────────────────────┬────────────────────┘  │
                     │                       │                       │
                     │         ┌─────────────┴─────────────┐         │
                     │         ▼                           ▼         │
                     │   scikit-learn ML              Gemini LLM     │
                     │   RandomForestClf (On-time)    (Strict JSON,  │
                     │   RandomForestReg (Hours)      Offline Cache, │
                     │   Feature Importances ("Why")  asyncio gather)│
                     └───────────────────────┬───────────────────────┘
                                             │
                                             ▼
                     ┌───────────────────────────────────────────────┐
                     │       Database: PostgreSQL (asyncpg)          │
                     │   (Normalized tables: weights, logs, etc.)    │
                     └───────────────────────────────────────────────┘
```

* **Frontend**: React 19, Vite, Tailwind CSS, Recharts, Lucide Icons (in `/frontend`).
* **Backend**: FastAPI (Python async), SQLAlchemy 2.0, and PostgreSQL through `asyncpg` (in `/backend`).
* **Machine Learning**: `scikit-learn` trained on student task history rows:
  * `RandomForestClassifier` for on-time completion probability (94.55% test accuracy).
  * `RandomForestRegressor` for actual hours required (1.23h MAE, $R^2 = 0.9813$).
  * Exposes `feature_importances_` to explain "The Why" in the UI.
* **LLM Engine & Intent Pipeline**: Google Gemini API (`gemini-3.8-flash` / `gemini-3.1-flash-lite`) called **exclusively from the backend**. Strict JSON schema parsing, intent classification (`message_intent`, `intent`), world fact lookup, 1 automated retry, and a persistent local fallback cache (`backend/data/demo_cache.json`).
* **Safety & Guardrails**: Integrated safety router (`safety.py`) providing non-diagnostic health guidance, crisis support routing, and content moderation prior to LLM processing.
* **Attachment Engine**: Document & text file extraction (`attachment_extractor.py`) supporting up to 5MB attachments with single-file UI enforcement.
* **Privacy Enforcement**: ONE central data gateway function (`get_permitted_user_data`). Any disabled source is never queried from storage and never injected into LLM context, with complete audit logging on every read (`audit_log`).
* **Web Push Notifications**: Automated 3-day and 1-day deadline reminders via Web Push (VAPID keys + service worker `sw.js`).
* **Autonomous Twin Proxy & Negotiator**: Autonomous meeting/task negotiation engine (`calendar_proxy.py`, `proxy_router.py`) that evaluates incoming requests against protected deep work focus blocks, timetable overlaps, and ML deadline collision risk to craft persona-aware counter-proposals.

---

##  Quickstart & Setup Guide

### 1. Prerequisites
* **Python 3.10+** (Tested on Python 3.14)
* **Node.js 18+** & npm
* **PostgreSQL 15+** with a running server and a database role that can create tables.

### 2. Backend Setup
```bash
# Navigate to the backend directory
cd backend

# Create and activate a virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create your .env file from the example
copy .env.example .env   # (or cp on Unix)
```

Create the application database once if it does not already exist:

```sql
CREATE DATABASE humantwin OWNER dev_user;
```

Edit `.env` to configure your keys:
```env
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=postgresql+asyncpg://YOUR_USER:YOUR_PASSWORD@localhost:5432/humantwin
PORT=8003
DEMO_MODE=true
```

URL-encode special characters in the password (for example, `@` as `%40`). PostgreSQL and the `humantwin` database must be running before startup. The backend will stop if `DATABASE_URL` is missing or points to another database. Even without an LLM API key, HumanTwin AI can use its bundled offline demo cache.

Return to the repository root before continuing with the commands below:
```bash
cd ..
```

### Background reminder notifications

Web Push lets opted-in users receive the 3-day and 1-day deadline reminders while the site is closed. It requires HTTPS on a deployed site (localhost is treated as a secure development origin), a browser that supports service workers and Push API, operating-system notifications enabled, and a running backend scheduler. The browser must be opened once to enable reminders and subscribe.

After installing the backend dependencies, generate a VAPID key pair once per environment:

```bash
python -m backend.scripts.generate_vapid_keys
```

Copy the printed `VAPID_PUBLIC_KEY` value into `backend/.env`, and set:

```env
VAPID_PRIVATE_KEY_PATH=data/vapid_private.pem
VAPID_SUBJECT=mailto:you@example.com
```

The generated private key is ignored by Git. Back it up securely and preserve the same key pair across restarts; replacing it invalidates existing browser subscriptions. After restarting the backend and frontend, open the Reminders bell and choose **Enable background reminders**. Reminder categories still need to be enabled in Privacy. The backend checks deadlines every minute and sends each reminder only once per lead time. Push delivery depends on the browser/OS push service and device notification settings.

### 3. Generate Seed Data & Train ML Models
```bash
# Seed the synthetic student persona (Alex Rivers) with 5 weeks of history
python -m backend.scripts.generate_data

# Seed optional working professional and freelancer personas
python -m backend.scripts.seed_persona_demos

# Train the on-time classifier and hours regressor models
python -m backend.ml.train
```

### 4. Start both parts of the app together (Windows)
```bash
cd ..
./run.bat
```
The launcher starts or reuses both services. The frontend is at `http://127.0.0.1:5173`; the backend API and Swagger docs are at `http://127.0.0.1:8003` and `http://127.0.0.1:8003/docs`.

To start the backend manually instead, run this from the repository root:
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8003 --reload
```

For a manual frontend start, open another terminal and run `npm install` once and then `npm run dev` from `frontend/`.

---

---

## Privacy & Data Sovereignty Guarantees

* **Single Data Access Gateway**: All endpoints query data through `get_permitted_user_data()`.
* **Zero Leaks**: If a user disables a category (e.g. Study Log), the SQL query does not load it, and Gemini never sees it.
* **Auditability**: Every data access transaction is recorded in the `audit_log` table with timestamps and source tracking.
* **Full Data Ownership**: Users have full CRUD access over their profile, timetable, deadlines, study logs, and preferences via the "Twin Knowledge" panel.
* **Local Persistence**: All application data is stored in PostgreSQL; no third-party telemetry is collected.

---

##  Contributors & Hackathon Prototype License

Built with ❤️ for the Hackathon by the **HumanTwin AI Team**.
Licensed under the MIT License.
