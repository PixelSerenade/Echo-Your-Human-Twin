# HumanTwin AI 🧠⚡

## Persona-aware memory

The backend registry in `backend/memory_registry.py` defines persona presets, category permissions, UI labels, prompt examples, and simulator dimensions. Existing timetable, deadline, focus-log, and preference tables remain in place and are exposed through generic memory categories, so existing rows and permission settings remain available. Startup adds the `users.persona` column with a `student` default and creates the new `goals` table without deleting existing data.

To add the synthetic working-professional and freelancer demo accounts to PostgreSQL, run `python -m backend.scripts.seed_persona_demos` from the repository root. The script is safe to rerun; existing demo accounts are left alone.

> **An intelligent digital twin that learns from permitted data, simulates "what-if" life scenarios, recommends balanced decisions, and evolves dynamically from user feedback.**

HumanTwin AI models a person through three internal thinking styles ("twins"):
* **Rational Twin**: Time, deadlines, workload, risk, practicality, and efficiency.
* **Emotional Twin**: Stress, happiness, motivation, comfort, peace of mind, and burnout prevention.
* **Ambitious Twin**: Career goals, professional differentiation, skill mastery, and long-term opportunities.

---

## 🏗️ System Architecture & Tech Stack

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
* **Machine Learning**: `scikit-learn` trained on 500+ student task history rows:
  * `RandomForestClassifier` for on-time completion probability (94.55% test accuracy).
  * `RandomForestRegressor` for actual hours required (1.23h MAE, $R^2 = 0.9813$).
  * Exposes `feature_importances_` to explain "The Why" in the UI.
* **LLM Engine**: Google Gemini API (`gemini-3.8-flash` / `gemini-3.1-flash-lite`) called **exclusively from the backend**. Strict JSON schema parsing, 1 automated retry on malformed outputs, and a persistent local fallback cache (`backend/data/demo_cache.json`).
* **Privacy Enforcement**: ONE central data gateway function (`get_permitted_user_data`). Any disabled source is never queried from storage and never injected into LLM context, with complete audit logging on every read.

---

## 🚀 Quickstart & Setup Guide

### 1. Prerequisites
* **Python 3.10+** (Tested on Python 3.13)
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

## 🧪 Running Automated Tests

Run the full end-to-end test suite (18 automated tests covering all 5 development phases):

```bash
# From the project root with the venv active:
pytest backend/tests/ -v
```

Tests verify:
1. **Phase 1**: Database schema initialization, synthetic persona seeding, single-gateway permission enforcement.
2. **Phase 2**: Honest ML model metrics, `/ask` response structure, strict privacy leak prevention (proving disabled data sources never reach Gemini context), and deadline risk flagging even for non-rational twins.
3. **Phase 3**: Simulator value clamping (0-100), non-linear diminishing returns, simulation correction persistence, mathematical weight renormalization, and the 3-consecutive 10-point lead primary switch rule.
4. **Phase 5**: Parallel `/debate` generation (`asyncio.gather`), council synthesis without single commands, and offline cache resilience.

---

## ⏱️ 2-Minute Hackathon Demo Script

Follow this script for an impactful 2-minute live presentation:

### Act 1: The Persona & Calibration (0:00 - 0:25)
1. **Show the Control Room Dashboard**:
   * Point out the top status bar: Alex Rivers (Computer Science student), with weights `50% Rational | 25% Emotional | 25% Ambitious`.
   * Explain: *"Alex's primary twin is Rational because they selected deadline-driven and risk-averse traits during onboarding."*
2. Click **"Configure Tags"**:
   * Show the grouped personality tags. Uncheck/check tags to demonstrate instant client-side calculation of the leading twin and weight distribution.

### Act 2: Fast Answer + The Planted Dilemma + ML Predictions (0:25 - 0:50)
1. Navigate to **"Ask Twin"**:
   * Click the planted dilemma pill: *"What if I spend two days on exam prep instead of the assignment?"*
   * Click **"Ask Primary Twin"**.
2. **Show the Real-World Deadline Collision Alert**:
   * Point out the amber alert: *"The Distributed Systems Midterm and Cloud Infrastructure Project are both due within 2.6 days (26.0h total effort required)."*
   * Emphasize: *"Even though Gemini generates the explanation, it never invents numbers. All figures come from the database and our trained scikit-learn ML models."*
3. **Show ML Prototype Indicators & "The Why"**:
   * Review the on-time probability gauge (23.3% prototype indicator) and predicted hours needed (16.4h vs 12.0h estimate).
   * Expand **"The Why" (ML Feature Importances)**: Show that `hours_remaining_until_due` (34.2%) and `estimated_hours` (27.8%) explain why the risk is severe.

### Act 3: On-Demand 3-Twin Council Debate (0:50 - 1:15)
1. Scroll down and click **"See the debate (Convene Council)"**.
2. Explain the backend architecture:
   * *"Instead of calling Gemini three times in series, the backend triggers parallel `asyncio.gather` calls for the Emotional and Ambitious twins, instructing them to add only what the Rational twin missed."*
3. **Step-by-Step Reveal**:
   * **Perspective 2 (Emotional Twin)**: Highlights anticipatory anxiety, burnout risk, and the importance of sleep and badminton.
   * Click **"Reveal Next Perspective"** $\rightarrow$ **Perspective 3 (Ambitious Twin)**: Argues that the Cloud Project is a portfolio differentiator for future architecture roles.
   * Click **"Reveal Council Synthesis"**: Show the **HumanTwin Council Synthesis** card.
   * Emphasize the core rule: *"The synthesis does not give a single command; it breaks down trade-offs (Time vs Energy, Short-term Relief vs Long-term Goals) and presents a balanced compromise option ('The Sprint-and-Build Integration')."*

### Act 4: Adaptive Personality Evolution (1:15 - 1:35)
1. Return to the question options and choose Option 3 (aligned with the **Ambitious Twin**).
2. Point out the live weight transition:
   * Ambitious weight increases by +0.12 (in demo mode) and renormalizes to sum to 1.0.
   * The consecutive lead counter increments (1/3).
3. Select an Ambitious option two more times:
   * On the 3rd consecutive decision with a 10+ point lead, the **"Your Twin Has Evolved!"** modal automatically appears with a before/after Recharts comparison.
   * Alex's primary twin switches from Rational $\rightarrow$ Ambitious!

### Act 5: Life Simulator & "Teach Your Twin" (1:35 - 1:50)
1. Navigate to **"Life Simulator"**:
   * Compare **Path A** (Deep Study 4h + Sleep 8h) vs **Path B** (Study 2h + Badminton 2h + Sleep 7h).
   * Click **"Simulate & Compare Scenarios"**:
   * Show side-by-side animated bars: Path B yields +15 higher energy and +22 higher happiness with minimal drop in study progress.
2. Demonstrate **"Teach Your Twin"**:
   * Under the correction box, enter: *"Badminton gives me 20% more focus for the next session."*
   * Click **"Save New Pattern"** $\rightarrow$ Show the **"New pattern learned"** confirmation badge, proving the twin customizes its physics engine to the user.

### Act 6: Privacy Control & Verifiable Audit Trail (1:50 - 2:00)
1. Navigate to **"Privacy & Audit"**:
   * Toggle off the **"Deadlines"** data source switch.
   * Show that the switch immediately updates the database.
2. Re-ask the question or inspect the **Audit Trail**:
   * Show the audit record proving that only permitted sources were read.
   * Reference the automated test `test_privacy_enforcement_disabled_source_never_sent_to_gemini`: *"We have automated tests mathematically guaranteeing that when a toggle is off, that data is never read and never sent to Gemini."*
3. Visit **"Twin Knowledge"**:
   * Show the full transparency memory inspector where Alex can view, edit, or delete any record stored in the twin.

---

## 🔒 Privacy & Data Sovereignty Guarantees

* **Single Data Access Gateway**: All endpoints query data through `get_permitted_user_data()`.
* **Zero Leaks**: If a user disables a category (e.g. Study Log), the SQL query does not load it, and Gemini never sees it.
* **Auditability**: Every data access transaction is recorded in the `audit_log` table with timestamps and source tracking.
* **Full Data Ownership**: Users have full CRUD access over their profile, timetable, deadlines, study logs, and preferences via the "Twin Knowledge" panel.
* **Local Persistence**: All application data is stored in PostgreSQL; no third-party telemetry is collected.

---

## 👥 Contributors & Hackathon Prototype License

Built with ❤️ for the Hackathon by the **HumanTwin AI Team**.
Licensed under the MIT License.
