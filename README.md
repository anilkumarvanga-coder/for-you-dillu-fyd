# FYD — For You Dillu

B.Pharmacy study companion using **Clerk + Supabase + OpenRouter + LangChain + Cognee**.

## Architecture

- **Next.js / Vercel:** FYD interface, Clerk session verification, same-origin API gateway.
- **Clerk:** login and account sessions. Enable Google in your Clerk instance. A server-side Clerk user ID allowlist restricts this installation to up to two approved accounts.
- **Supabase:** private originals, extracted pages, conversations, summaries, usage and durable job state. Uploads go directly to signed Supabase URLs; PDFs do not pass through Vercel request bodies.
- **Python API + one worker:** persistent services separate from Vercel. The API accepts only the trusted gateway secret plus its verified user identity. The worker claims PostgreSQL jobs and records progress.
- **LangChain:** chat/vision prompt orchestration through ChatOpenAI's OpenAI-compatible interface.
- **OpenRouter:** chat and page vision models, configured by model ID. No direct OpenAI API key required by FYD.
- **Cognee API:** one dataset per document; graph creation and scoped context retrieval. Works with a Cognee tenant endpoint exposing add/cognify/search/forget. Cognee itself needs its own model/embedding configuration and durable databases or a managed tenant; its expenses are separate from FYD's OpenRouter calls.

## Implemented workflow

Sign in → upload a PDF or images → background page extraction and vision → Cognee ingestion → ready → question, source-page preview or whole-document summary.

Every accepted PDF page is processed. Over-capacity/encrypted/invalid documents fail as a whole; there is no page-range selection or silent tail truncation. Vision also reads diagrams on text-heavy pages. Each page is labelled with its document UUID and page number before Cognee ingestion. Answers are generated from retrieved context; citations are model-generated and should be checked against the provided Pages preview. The application does not yet independently prove that a citation supports a claim.

Summaries run through all extracted pages in bounded groups, followed by hierarchical reduction. They are separate from question retrieval. Summary/source previews shown in the current chat can be exported; these preview messages are not appended to the saved conversation. Successful question/answer exchanges are stored atomically.

Deletion runs in the worker: remove the document's Cognee dataset, original storage object, extracted pages, and summary. Deletion failures remain visible and can be retried with Delete. Existing chat answers remain until separately managed; deleting a file does not erase copies in conversation text or provider retention systems.

## 1. Supabase

Run `supabase/002_final_stack.sql` once in the SQL Editor. It is additive and preserves legacy tables from the initial app. The migration creates a private `fyd-documents` bucket and server-only tables with RLS. No Clerk-to-Supabase JWT integration is needed because browser data-table queries are not used. Signed upload tokens authorize only a particular object.

Use a **direct PostgreSQL connection or session-mode pooler**, with SSL enabled, for `DATABASE_URL`. Do not use transaction-mode pooling: the single-worker advisory lock requires a session connection. Use a server database role with access to the FYD tables; never place this connection string in browser variables.

## 2. Clerk

Create a Clerk application, enable Google login, and configure the deployed website's domain. Fill the frontend `.env.example` values. Sign in with each of the two intended Google accounts to create their Clerk users. Before approval they can authenticate but cannot access FYD documents or AI. In Clerk Dashboard → Users, copy each account's `user_...` ID. Set `ALLOWED_CLERK_USER_IDS=user_FIRST,user_SECOND` on both Vercel and the Python API/worker environment. Redeploy/restart those services. One or two unique IDs are accepted; empty, malformed or more than two IDs deny all access. The legacy singular variable is supported only when the plural variable is absent. Each account has separate documents, chats, summaries and operation quotas. Cognee search sessions are scoped by account and conversation. This is application access control, not a Clerk signup block: other people may create Clerk accounts but cannot use the study APIs. If you also want to block registration, configure Clerk's signup restrictions separately; plan requirements can apply. Existing Supabase-auth accounts and browser-local chats are not automatically migrated.

## 3. Cognee and OpenRouter

Provision a Cognee tenant or your own compatible authenticated API. Set `COGNEE_URL` to its base URL (without `/api/v1`) and `COGNEE_API_KEY` to its API key. This adapter uses `X-Api-Key`. A self-hosted instance must support that authentication contract or sit behind an authenticated gateway; do not expose an unauthenticated instance.

Configure Cognee's own LLM and embedding provider explicitly in its deployment. FYD's OpenRouter environment variables do not configure a remote Cognee tenant. Use a tested Cognee release supporting synchronous `cognify` with `run_in_background:false`, dataset-scoped `GRAPH_COMPLETION` search with `only_context:true`, and dataset-scoped `forget`. Endpoint compatibility and returned job status must be tested against the provisioned tenant before production.

Create an OpenRouter key. Configure text and image-capable models in `backend/.env`; the example uses `openai/gpt-4.1-mini`. Select the desired provider data policy and set a key credit limit. Page vision, graph extraction, embeddings and answers can all incur costs. The operation quota is not a currency budget.

## 4. Python deployment

Copy `backend/.env.example` to `backend/.env` and fill it securely. Generate a random shared gateway secret of at least 32 bytes; set the same `FYD_BACKEND_SECRET` in Vercel and Python.

```sh
cd backend
docker compose up --build -d
```

Compose binds the API to localhost. For hosting, run the Dockerfile as an HTTPS web service and a second service with command `python -m fyd.worker`. Run **one worker replica**. PostgreSQL stores job state; originals live in Supabase and Cognee owns its graph persistence. A session advisory lock prevents a second worker from interfering. Interrupted processing jobs become failed on restart and can be retried. A retried ingestion currently reprocesses the complete document and can incur costs again.

Use a host supporting long-running processes, outbound HTTPS and PostgreSQL session connections. Configure health checks against `/health`, restricted ingress where possible, HTTPS termination, restart policies, logs and database backups. `/health` is liveness only, not proof of provider connectivity. The API logs no document contents; job failures log exception class and job ID.

## 5. Vercel

Set every frontend `.env.example` variable in Vercel, including your HTTPS Python service URL. `FYD_BACKEND_SECRET` and `CLERK_SECRET_KEY` stay server-only. Supabase's URL and anon key are public; its service-role key stays only on Python.

```sh
npm ci
npm run build
```

Redeploy after setting Clerk public configuration. Authenticated gateway calls have a 300-second maximum duration; document ingestion and summaries run outside the request. The existing `/api/chat` endpoint returns 410 and cannot bypass Clerk.

## Limits and operations

- One PDF or up to five images per selection; 20 MB per file, at most 500 PDF pages. Complete over-limit PDFs are rejected; no pages removed.
- 30 charged operations/day and 300/month, UTC. Upload reservations, retries, summary requests and chat attempts consume operations. An upload includes all of its page processing; one operation can involve hundreds of paid calls. Failed attempts count.
- Up to five ready documents per question. Last 12 conversation messages are supplied as history.
- Library/conversation lists currently display the newest 100 entries.
- Extraction progress shows pages completed; graph processing remains processing until completion. File upload progress is a stage label, not byte percentage.
- Original files are cloud stored now; this replaces the initial phone-only design. Content also reaches the configured model and Cognee services.
- Original book licensing remains the uploader's responsibility; no bundled book collection.

## Verification and release gate

```sh
npm run typecheck
npm run build
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.lock.txt
.venv/bin/python -m pytest -q
```

Automated local checks cover backend identity rejection, owner-scoped document lookup and preservation of all text through summary grouping. They do not substitute for live integration tests.

**Before calling this production-ready:** configure the accounts, deploy the API and worker, run the migration, then verify allowed/denied Clerk accounts, a text PDF, a scanned PDF, a diagram image, last-page extraction, Cognee job completion/retrieval, source references, multi-image upload, summary, restart/retry, deletion across stores, persistence after sign-out, and actual billed usage. Live services were not available during this implementation. No claim of a fully validated deployment is made.

Provider docs used: https://clerk.com/docs/reference/nextjs/app-router/auth • https://docs.cognee.ai/api-reference/introduction • https://supabase.com/docs/reference/javascript/storage-from-uploadtosignedurl • https://openrouter.ai/docs
