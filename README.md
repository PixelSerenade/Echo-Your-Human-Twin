# Echo — Your Human Twin

> **Project status: In progress.**

Echo is a personal digital twin that remembers the information you choose to share, helps you make decisions, creates plans, tracks goals, and sends reminders. It can answer in a rational, emotional, or ambitious voice while keeping each account's data separate.

## Features

- Chat with Echo using Google Gemini.
- Persistent conversations, memories, goals, commitments, and deadlines.
- Preparation plans with timetable blocks and checkable goal steps.
- Today and This Week planning views.
- Optional Spending & Money tracking.
- PDF and document upload for explanations and quizzes.
- Hear other twin voices when you want another perspective.
- Privacy controls for each memory category with consent records and audit logs.
- Browser push reminders for saved deadlines and scheduled blocks.
- Twin Proxy for evaluating meeting requests against protected focus blocks.

## Technology

- React, Vite, and Tailwind CSS frontend.
- FastAPI and SQLAlchemy backend.
- PostgreSQL database.
- Google Gemini API for conversational responses and planning.

## Requirements

- Python 3.10 or newer
- Node.js 18 or newer
- PostgreSQL 15 or newer
- A Google Gemini API key

## Local setup

1. Create a PostgreSQL database and a user with permission to create tables.
2. Create `backend/.env` from `backend/.env.example` and set:

   ```env
   GEMINI_API_KEY=your_gemini_api_key
   DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@localhost:5432/humantwin
   ```

3. Install backend dependencies:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   cd ..
   ```

4. Install frontend dependencies:

   ```powershell
   cd frontend
   npm install
   cd ..
   ```

5. Start both services on Windows:

   ```powershell
   .\run.ps1
   ```

Open `http://127.0.0.1:5173/`.

## Deployment

Echo runs as one Railway service with PostgreSQL:

<https://echo-your-human-twin-production.up.railway.app>

Set `GEMINI_API_KEY` and `DATABASE_URL` as private Railway variables. Keep the `/data` volume attached so sessions, uploads, and notification keys survive redeployments.

## Privacy

Echo only reads memory categories that a user has enabled. Account data is stored separately in PostgreSQL. Users can review, change, or delete saved information from the app.

## License

MIT License.
