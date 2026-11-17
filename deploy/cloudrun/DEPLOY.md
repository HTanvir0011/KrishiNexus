# Hosted demo: Render (free) or Google Cloud Run

One container serves the built frontend and the API on one origin, on the host's `$PORT`. `serve.py` does in one
process what `frontend/nginx.conf` and the two compose containers do locally. The host builds the `Dockerfile` itself,
so no local Docker is needed. The Dockerfile downloads this repository's `main` branch from GitHub. The trained models
are git-ignored, so the demo runs the labelled fallbacks.

Hardening for a public URL, all in `serve.py`:
- These writes are limited to 30 a minute per visitor, then answer 429:
  - `POST /market/bids/lock`;
  - `POST /automation/*` (truck-pool joins, resets and transit checks, and the n8n jobs);
  - `POST /mcp/simulate-anomaly` and `DELETE /mcp/anomalies`;
  - `POST /feedback`.
- The visitor is the rightmost public address in `X-Forwarded-For`, which the host's proxy saw; addresses the client
  writes before it are ignored.
- CORS admits no other origin (`KNX_CORS_ORIGINS` is empty), because the page and the API share the service's origin.
- Receipts, certificates and login sessions are signed with `KNX_RECEIPT_SIGNING_KEY`. Render generates a stable one
  (`render.yaml`); elsewhere `serve.py` makes a random key per start, because the default key is public on GitHub.
- Responses are gzipped: an open `/os` tab polls the API every few seconds, about 5.8 MB an hour raw and 1.1 MB
  gzipped.

Check `serve.py` without Docker: `backend/.venv/Scripts/python deploy/cloudrun/check_serve.py`.

## Render (free, recommended)

`render.yaml` at the repository root describes one free web service, `krishinexus-os`, in Singapore (the nearest
Render region to Dhaka).

What the free plan gives, from Render's docs (November 2026):
- 0.1 CPU and 512 MB of memory. The app uses about 130 MB, but the slow CPU makes the first answer after a wake-up
  take several seconds.
- It sleeps after 15 minutes without traffic (an open page's WebSocket pings count as traffic), and the next visitor
  waits about a minute while it wakes.
- 750 free instance hours a month per workspace, and 5 GB of outbound bandwidth on the free Hobby workspace.
- The docs ask for no card to deploy a free service. Without a payment method, going over a limit suspends the service
  for the rest of the month instead of charging.
- The disk is wiped whenever the service restarts or sleeps, so accounts, truck pools, escrows and feedback start
  fresh. Render may restart a free service at any time.

### Deploy

1. In GitHub Desktop, commit and push the repository, including `render.yaml` and `deploy/`. The build downloads
   `main`.
2. At render.com, sign up with your GitHub account.
3. In the Render dashboard, choose **New → Blueprint**, connect the `HTanvir0011/KrishiNexus` repository, review the
   one free web service it lists, and choose **Deploy Blueprint**. If the dashboard says the free plan isn't offered in
   Singapore, change `region: singapore` to `frankfurt` in `render.yaml`, push, and try again (the region can't be
   changed after the service exists).
4. Watch the build in the service's **Logs**; it takes several minutes (it builds the frontend and installs the
   backend). The service's page then shows its URL, `https://krishinexus-os.onrender.com` or the same name with a
   suffix if that one is taken. Give the judges that URL.

### Keep it awake during judging (optional)

The workflow `.github/workflows/keep-demo-awake.yml` calls `/health` every 10 minutes, so a judge never meets the
one-minute wake-up. It does nothing until you turn it on:

1. On GitHub, open the repository's **Settings → Secrets and variables → Actions → Variables** and add a repository
   variable `DEMO_URL` with the Render URL.
2. To stop it after judging, delete the variable.

Awake all month, the service uses about 720 of the 750 free hours, so don't run another free service in the same
Render workspace while it is on. GitHub sometimes starts scheduled runs late, so an occasional wake-up can still happen.

### Run it

- Update: push to `main` (GitHub Desktop: **Commit to main**, then **Push origin**). A service created from the
  public repository URL, as `tanvir.health` is, doesn't see pushes, so `.github/workflows/deploy-render.yml` calls its
  deploy hook. Set it up once: in Render, open the service's **Settings → Deploy Hook** and copy the URL; on GitHub, open
  **Settings → Secrets and variables → Actions → New repository secret**, name it `RENDER_DEPLOY_HOOK` and paste the
  URL. Every push then redeploys (5–10 minutes); the repository's **Actions** tab shows each run. Without the secret,
  use the service's **Manual Deploy → Deploy latest commit**.
- Reset the demo state: restart the service from its page in the dashboard, or let it sleep.

## Check the hosted demo

```bash
URL=https://krishinexus-os.onrender.com
curl -s $URL/health
curl -s -o /dev/null -w "%{http_code}\n" $URL/os/field
curl -s $URL/api/docs | grep -c swagger-ui
for i in $(seq 31); do curl -s -o /dev/null -w "%{http_code} " -X POST $URL/market/bids/lock -H "Content-Type: application/json" -d "{}"; done; echo
```

Expect `"status":"ok"`, `200`, `1`, then thirty `422` and one `429`. The last check blocks your own writes for a
minute. If no `429` appears, the limiter is not seeing one address per visitor; report it before judging starts.
While you are blocked, a write from another network (a phone hotspot) should still get `422`; if it gets `429`,
the limit is shared by every visitor, which is safe but stricter. Then open `/os`, run a farmer request, and watch
the agent trace stream in the command centre (a WebSocket).

## Google Cloud Run (alternative)

Cloud Run needs a Google Cloud project with billing turned on (a card), but gives a full CPU.

1. Push the repository, including `deploy/`, to GitHub. The build downloads `main`.
2. At console.cloud.google.com, create a project (for example `krishinexus-demo`) and link a billing account (a
   card; new accounts get trial credit). Under Billing → Budgets & alerts, create a $5 budget with email alerts.
3. Install the Google Cloud CLI (cloud.google.com/sdk/docs/install), run `gcloud init`, sign in and choose the
   project.
4. Let Cloud Build deploy to Cloud Run. Get the project number with
   `gcloud projects describe <project-id> --format="value(projectNumber)"`, then run:

```bash
gcloud projects add-iam-policy-binding <project-id> --member="serviceAccount:<project-number>-compute@developer.gserviceaccount.com" --role="roles/run.builder"
```

5. From the repository root, deploy. Answer `y` when gcloud offers to enable the Cloud Run, Cloud Build and Artifact
   Registry APIs and to create the `cloud-run-source-deploy` repository.

```bash
gcloud run deploy krishinexus-os --source deploy/cloudrun --region asia-south1 --allow-unauthenticated --max-instances 1 --concurrency 250 --timeout 3600
```

6. The command prints the service URL (`https://krishinexus-os-….asia-south1.run.app`). Give the judges that URL, and
   run the checks above against it.

What the flags do:
- `--allow-unauthenticated` makes the URL public.
- `--max-instances 1` keeps every visitor on one instance, since the demo state lives in memory. It also caps the
  bill at one instance.
- `--concurrency 250` lets one instance hold every open tab, because each tab keeps a WebSocket open.
- `--timeout 3600` lets a WebSocket stay open 60 minutes (the maximum) before the page reconnects.
- asia-south1 (Mumbai) is the closest region to Dhaka and is priced as Tier 1.

Cost:
- Each open tab keeps a WebSocket to the trace stream. Cloud Run bills an instance for as long as any WebSocket is
  open, so the service is billed whenever at least one visitor has the page open.
- The monthly free tier covers roughly 50 to 65 such hours at 1 vCPU and 512 MiB. After that it costs about
  $0.07 an hour; these are third-party figures, because Google's pricing page could not be read when this was
  written.
- With one instance at most, a tab left open all month costs about $50. The budget alert warns long before that.
- When no one has had the page open for 15 minutes, the instance stops. The next visitor waits a few seconds for
  it to start, and the demo state (truck pools, escrows, injected anomalies, storage bookings) starts fresh.
- Update by pushing to GitHub and running the deploy command again. After judging, delete the service:

```bash
gcloud run services delete krishinexus-os --region asia-south1
```
