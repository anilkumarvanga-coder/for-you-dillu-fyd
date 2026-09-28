# FYD

**For You Dillu** — a personal B.Pharmacy study companion, built with Next.js for Vercel.

## Included in this first version

- Responsive green-and-cream FYD study workspace, mobile layout, Markdown answers.
- Google sign-in through Supabase; server verifies the session and restricts AI access to one configured, verified Google email.
- OpenAI Responses API chat with follow-up context (last 20 messages).
- One complete PDF or up to five JPG/PNG/WebP images per question. Files stay selected for follow-ups. No page-range selector or silent page truncation.
- Combined attachment size about 2.8 MB; the server strictly caps the serialized request at 4 MB for Vercel. Large conversation context can reduce the available attachment size. This is not unlimited upload support.
- Whole PDF sent directly to the model, including scanned pages. Very large page counts, encrypted PDFs, unreadable scans, or model context overflow can fail explicitly even when byte size is small. No background indexing or large-book retrieval yet.
- Chat text saved on this browser/device, per signed-in user; Markdown export. Original attachments are held only in browser memory and need reselecting after refresh. No Google Drive integration.
- Database-enforced 30 AI attempts per UTC day, 300 per UTC month, and a 10-second minimum interval. Failed provider attempts count to prevent repeated spending. These request limits are NOT a currency spending cap; whole PDF requests can consume many tokens.

There are no preloaded copyrighted books. Upload material you are authorized to use. This is educational support, and generated facts/citations need verification.

## Setup

1. Use Node.js 22.13+ (Node 24 recommended). Run `npm ci`.
2. Copy `.env.example` to `.env.local` and fill every value. Do not commit secrets.
3. Create a Supabase project. Run `supabase/schema.sql` in its SQL Editor.
4. In Supabase Authentication, enable Google. Create Google OAuth credentials, using the Supabase callback URL shown in that provider setup. Keep other sign-in providers disabled for this single-student app.
5. Set Supabase Site URL to your final Vercel URL. Add that exact URL and `http://localhost:3000` to allowed redirect URLs. Add corresponding authorized JavaScript origins in Google if requested by its setup.
6. Set `ALLOWED_STUDENT_EMAIL` to the student's Google account. This is a SERVER variable; it is not assumed to be the repository owner's email.
7. Add an OpenAI API key with available API billing. ChatGPT Plus does not supply API credits. `OPENAI_MODEL` defaults to `gpt-4.1-mini`. Set provider budget alerts and monitor usage; alerts may not be hard caps.
8. Run `npm run dev`, sign in, and ask a small question. Test an actual PDF and image before relying on study answers.

Only `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` are public. Never prefix service-role or OpenAI keys with `NEXT_PUBLIC_`. The SQL usage table has RLS enabled, no browser access, and a service-role-only quota function.

## Deploy to Vercel

Import this GitHub repository as a Next.js project. Use the default build command `npm run build`. Add the same environment variables in Vercel, then deploy. Update Google/Supabase redirect configuration to the final URL and redeploy if any public variables change. Preview deployments need their own explicitly allowed redirect URL if you want login on them.

The interface can render without configuration, but sign-in and AI operations require setup. Missing server configuration fails closed. The API uses Node runtime and a 60-second function duration. Do not expose this app publicly for general AI usage without revisiting access control and cost limits.

## Data flow and privacy

Browser → FYD server → OpenAI: question, recent chat context, and selected attachments. Supabase stores account/session data and usage counts, not study files or chats. The browser retains chat text until replaced or browser data is cleared. Export before using New study session. Signing out hides the conversation but does not erase browser storage. `store: false` is used for model responses; provider abuse-monitoring retention can still apply. No AI requests or full file contents are logged by this application.

PDF citations are model-generated page references, not independently validated clickable citations. Keep your original textbook for verification. Repeated questions resend the selected files and incur additional input usage.

## Checks

```sh
npm test
npm run typecheck
npm run build
```

Unit tests cover attachment policy, mixed files, count limits, encoding, and size. Live Google OAuth, database quota concurrency, and paid model calls require the configured services and have not been exercised in the initial implementation. Before use, verify: wrong Google account is rejected, unauthenticated API calls return 401, quota rejects rapid/repeated calls, and your PDF's last page can be referenced in an answer.

## Next improvements

Persistent local document library, resumable whole-document indexing for larger textbooks, stronger verified citations, visible remaining usage, conversation history sidebar, and additional integration tests. These are not implemented in this first commit.
