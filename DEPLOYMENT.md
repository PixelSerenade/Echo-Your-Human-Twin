# Deploy Echo on Railway

The root Dockerfile builds the React frontend and serves it through FastAPI at
one HTTPS URL. The backend uses a single PostgreSQL database. No local database
records or uploaded files are copied into the image.

1. Create a Railway project and deploy this GitHub repository as a service.
   Keep the repository root as the service root; Railway reads `railway.json`.
2. Add a PostgreSQL service to the same project.
3. Attach a persistent volume to the Echo service at `/data`. This stores uploads,
   the session signing secret, and the VAPID key. Preserve this volume on redeploy.
4. Configure these service variables:

   | Variable | Value |
   | --- | --- |
   | `DATABASE_URL` | Reference the PostgreSQL service's `DATABASE_URL`, e.g. `${{Postgres.DATABASE_URL}}` |
   | `GEMINI_API_KEY` | Your Gemini key, entered privately in Railway |
   | `VAPID_SUBJECT` | `mailto:` followed by your contact email |

   The Dockerfile sets `PRODUCTION=true`, `DEMO_MODE=false`, `DATA_DIR=/data`, and
   `STATIC_DIR=/app/frontend/dist`. Railway supplies `PORT`. Secrets are generated
   on the persistent volume unless explicitly provided as private variables.
5. Generate a public domain for the Echo service. Use one replica with sleeping
   disabled so the reminder scheduler keeps running. The database remains private.
6. Check `/health`, sign up, finish onboarding, and enable notifications in the bell.
   Send a test notification, then test a scheduled block on a real device.

Production requires signed, expiring HTTPS session cookies. Every protected API
route checks that supplied account IDs match the signed-in account. Local demo
authentication is disabled in the container. The frontend uses the deployed
origin for API requests, so there is no localhost address in the hosted request path.

Railway account access and sufficient hosting credits are required to create the
services and volume. Review costs in your Railway workspace before activating a
paid plan. This file does not provision or purchase any resources by itself.

References: [Railway Dockerfiles](https://docs.railway.com/guides/dockerfiles),
[variables](https://docs.railway.com/variables),
[volumes](https://docs.railway.com/volumes).
