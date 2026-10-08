# FYD on Oracle Cloud Always Free

This deploys the Python API, one background worker and Caddy HTTPS proxy. Vercel still hosts Next.js. Supabase stores data; the configured Cognee tenant remains external. It does not provision Oracle resources or a Cognee server automatically.

## 1. Create the account and VM

Sign up at https://www.oracle.com/cloud/free/ and complete identity/card checks yourself. Remain on the free account unless you deliberately decide otherwise. Select your home region carefully: Always Free capacity is region-dependent.

In OCI Console: Compute → Instances → Create instance.

- Name: `fyd-backend`.
- Image: Canonical Ubuntu 24.04 LTS, ARM-compatible for A1.
- Shape: `VM.Standard.A1.Flex`, explicitly Always Free eligible.
- Initial size: 1 OCPU, 6 GB RAM. This leaves room within the currently documented Always Free tenancy aggregate of 2 OCPUs / 12 GB. Count all other instances in the tenancy. Check the console's current eligibility and estimate before creating.
- Boot volume: default approximately 50 GB, within your remaining Always Free block-volume allowance. Do not enable paid performance/backups/options accidentally.
- Networking: public subnet, internet gateway/route, and a public IPv4 address.
- SSH: generate a key pair in OCI or supply your own public key. Save the private key locally, never in GitHub or chat.

Capacity shortages can prevent provisioning. Do not substitute a paid shape just to bypass this. Idle Always Free instances can be reclaimed; keep durable data in Supabase and Cognee and preserve deployment configuration.

## 2. Network and SSH

Use OCI security lists or a network security group:

| Destination TCP port | Source | Purpose |
|---|---|---|
| 22 | Your current public IP with /32 | SSH administration |
| 80 | 0.0.0.0/0 | HTTPS certificate validation/redirect |
| 443 | 0.0.0.0/0 | Public HTTPS API |

Do not expose 8000 or PostgreSQL from the VM. The Compose file publishes only Caddy. OCI network rules and the guest OS firewall both matter. Inspect the Ubuntu image firewall before adding narrowly scoped rules; do not flush or disable it. Docker-published ports can bypass UFW, so keep OCI ingress restricted to the table above.

From your laptop (replace the filenames/IP):

```sh
chmod 600 ~/Downloads/fyd-private.key
ssh -i ~/Downloads/fyd-private.key ubuntu@YOUR_VM_IP
```

Verify the host fingerprint using the console/instance information before accepting an unfamiliar host key. Do not disable SSH host-key checks.

## 3. Docker and source

Install Docker Engine and the Compose plugin using Docker's official Ubuntu apt-repository instructions: https://docs.docker.com/engine/install/ubuntu/ . Choose the detected architecture; A1 is arm64. Avoid third-party install scripts.

```sh
sudo apt update
sudo apt install -y git
git clone --branch feat/final-stack https://github.com/anilkumarvanga-coder/for-you-dillu-fyd.git
cd for-you-dillu-fyd
```

After the upgrade merges, use the corresponding main release instead. This configuration has not been exercised on an Oracle ARM VM; validate the Docker image build and dependencies there before enabling live usage.

## 4. Environment and database

Run `supabase/002_final_stack.sql` once in Supabase SQL Editor. Do not rerun it against existing tables without a migration review.

```sh
umask 077
cp backend/.env.example backend/.env
cp deploy/oracle/.env.example deploy/oracle/.env
nano backend/.env
nano deploy/oracle/.env
chmod 600 backend/.env deploy/oracle/.env
```

Fill all backend values using the root README. Generate the shared gateway secret locally with `openssl rand -hex 32`; paste it into the private backend env file and Vercel settings. Do not put real credentials in command arguments or commit them.

Use a direct PostgreSQL connection or a session-mode Supabase pooler, with SSL. The worker holds a session advisory lock; transaction-mode poolers are incompatible. Use the same two approved Clerk IDs on Python and Vercel.

## 5. HTTPS hostname

Set a DNS A record for a hostname you control, such as `api.yourdomain.com`, to this VM's public IPv4. Set `FYD_API_DOMAIN` to that hostname in `deploy/oracle/.env`.

Your `*.vercel.app` hostname belongs to the frontend and cannot be repointed as your Oracle API hostname. If you have no domain/subdomain, arrange a DNS hostname before proceeding with this HTTPS configuration. Domain registration may cost money; this guide does not assume one is free.

Caddy obtains/renews certificates once DNS and ports 80/443 work. Its named volumes retain certificate state; do not delete them during routine updates.

## 6. Start and verify

Run from `deploy/oracle` so Compose picks up its `.env`:

```sh
cd deploy/oracle
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose ps
sudo docker compose logs --tail=50 api worker proxy
```

Use `config --quiet`, not plain `config`: expanded configuration can include credentials. Review logs privately; redact credentials and personal data before sharing.

Open `https://YOUR_API_HOSTNAME/health`; expect `{"status":"ok"}`. An unauthenticated request to `/documents` should return 401. Health only confirms the API process, not live provider integrations.

Set Vercel `FYD_BACKEND_URL=https://YOUR_API_HOSTNAME`, the matching secret, both Clerk IDs, and frontend keys. Redeploy the upgrade branch. Verify both approved accounts and a denied account, then a small PDF/image, last-page extraction, Cognee search, summary and deletion. Watch provider billing while testing.

## Updates and recovery

```sh
# At repository root, after reviewing remote changes:
git pull --ff-only
cd deploy/oracle
sudo docker compose up -d --build
```

Do not start the old `backend/compose.yaml` stack alongside this one. Worker exclusivity is enforced using a database advisory lock. Interrupted jobs become failed and can be retried in FYD. Restart policies recover exited processes; liveness healthchecks do not prove a worker is making progress. Monitor queued/processing jobs and failures in Supabase and worker logs.

Keep Supabase/Cognee backups independent of this VM. Protect environment files and SSH keys. If OCI reclaims the VM, recreate it, restore configuration, repoint DNS, and start this stack.

Free VM eligibility is not a guarantee of zero total application cost: OpenRouter, Cognee hosting/processing, domain registration and usage above provider allowances remain separate.

Official references: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm • https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/launchinginstance.htm • https://caddyserver.com/docs/running
