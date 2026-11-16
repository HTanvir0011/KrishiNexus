# Hosted demo on Google Cloud Run

One container serves the built frontend and the API on one origin, on Cloud Run's `$PORT`. `serve.py` does in one
process what `frontend/nginx.conf` and the two compose containers do locally. `gcloud run deploy --source` uploads
this folder and Google builds the `Dockerfile`, so no local Docker is needed. The Dockerfile downloads this
repository's `main` branch from GitHub. The trained models are git-ignored, so the demo runs the labelled fallbacks.

Hardening for a public URL, all in `serve.py`:
- These writes are limited to 30 a minute per visitor, then answer 429:
  - `POST /market/bids/lock`;
  - `POST /automation/*` (truck-pool joins, resets and transit checks, and the n8n jobs);
  - `POST /mcp/simulate-anomaly` and `DELETE /mcp/anomalies`.
- The visitor is the rightmost public address in `X-Forwarded-For`, which Google's proxy saw; addresses the client
  writes before it are ignored.
- CORS admits no other origin (`KNX_CORS_ORIGINS` is empty), because the page and the API share the service's origin.
- Receipts and certificates are signed with a random key per start, because the default key is public on GitHub.

Check `serve.py` without Docker: `backend/.venv/Scripts/python deploy/cloudrun/check_serve.py`.

## Deploy

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

6. The command prints the service URL (`https://krishinexus-os-….asia-south1.run.app`). Give the judges that URL.

What the flags do:
- `--allow-unauthenticated` makes the URL public.
- `--max-instances 1` keeps every visitor on one instance, since the demo state lives in memory. It also caps the
  bill at one instance.
- `--concurrency 250` lets one instance hold every open tab, because each tab keeps a WebSocket open.
- `--timeout 3600` lets a WebSocket stay open 60 minutes (the maximum) before the page reconnects.
- asia-south1 (Mumbai) is the closest region to Dhaka and is priced as Tier 1.

## Check it

```bash
URL=https://krishinexus-os-<...>.asia-south1.run.app
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

## Cost

- Each open tab keeps a WebSocket to the trace stream. Cloud Run bills an instance for as long as any WebSocket is
  open, so the service is billed whenever at least one visitor has the page open.
- The monthly free tier covers roughly 50 to 65 such hours at 1 vCPU and 512 MiB. After that it costs about
  $0.07 an hour; these are third-party figures, because Google's pricing page could not be read when this was
  written.
- With one instance at most, a tab left open all month costs about $50. The budget alert warns long before that.
- When no one has had the page open for 15 minutes, the instance stops. The next visitor waits a few seconds for
  it to start, and the demo state (truck pools, escrows, injected anomalies, storage bookings) starts fresh.

## Run it

- Update: push to GitHub, then run the deploy command again.
- Reset the demo state: run the deploy command again, or let the instance stop.
- After judging, delete the service so nothing more is billed:

```bash
gcloud run services delete krishinexus-os --region asia-south1
```
