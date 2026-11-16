# Steady Days × OpenReply Setup Kit

This folder holds the configuration template and campaign spec for running **Comment `CALM` → Free Chapter 1 DM** using [OpenReply](https://github.com/diwenne/openreply).

Because OpenReply requires a persistent Next.js web server (for Meta webhooks), a long-running BullMQ worker (`npm run worker`), PostgreSQL, and Redis, it runs alongside this repo rather than inside GitHub Actions.

## Files in this folder
- `.env.example` — Exact environment variables required for Vercel (web app) and Railway/Render (worker + Postgres + Redis).
- `campaign_calm.json` — Ready-to-copy campaign settings for the `CALM` keyword trigger and Free Chapter 1 link.

## Quick Deploy Order
1. **Fork** `https://github.com/diwenne/openreply` to your `swaltnuscord-sketch` GitHub account.
2. **Deploy Worker + Postgres + Redis** (e.g. Railway):
   - Add **PostgreSQL** and **Redis** (must support blocking commands; HTTP-only Redis will not work with BullMQ).
   - Add the forked repo as a worker service:
     - Build Command: `npm run db:generate`
     - Start Command: `npm run worker`
   - Run `DATABASE_URL="<public_postgres_url>" npm run db:migrate` once from your machine.
3. **Deploy Web App** (Vercel):
   - Import your `openreply` fork to Vercel.
   - Set the shared environment variables from `.env.example` (keep `ENCRYPTION_KEY` identical across web and worker, and use public DB/Redis URLs on Vercel).
4. **Choose Instagram Connection**:
   - **Direct Meta App** (free, no Zernio fee): Create a Business Meta app with **Manage messaging and content on Instagram** (Instagram Login), add `@Steady.Days.Ebooks` as an Instagram tester and accept in the Instagram app, set OAuth redirect `https://<your-app>.vercel.app/api/instagram/callback`, set webhook `https://<your-app>.vercel.app/api/webhook` (subscribe to `comments` and `messages`), add `/privacy`, `/terms`, and `/data-deletion` URLs, and switch the app to **Live**.
   - **Zernio** (optional paid connector): Save your Zernio API key in OpenReply Settings to skip Meta app setup.
5. **Create the `CALM` Campaign**:
   - Paste the copy and UTM link from `campaign_calm.json` into the OpenReply dashboard and test from a second Instagram account.
