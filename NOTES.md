# BuyBot — Session Notes

Azure deployment of the price-comparison app: frontend on the public VM,
FastAPI backend + Postgres on the private VMs, Ansible master as jump box.

---

## Architecture (CORRECTED — the real app)

```
Browser → http://<public_vm_ip>:3000           (frontend, public VM)
   │  SPA calls same-origin  /api/*  (VITE_API_BASE_URL=/api, baked at build)
   ▼
Nginx (inside frontend container, port 3000)
   │  location /api/ → proxy_pass http://<backend_private_ip>:8000   (over VNet)
   ▼
FastAPI backend  (uvicorn app.main:app, port 8000)   on private VM
   ├── Postgres container (private-db, same docker network "azure-net")
   └── SerpAPI (outbound, Google Lens for image search + Google Shopping)
```

- **Backend is Python/FastAPI** (`backend/app/`, `app.main:app`), NOT the old Node
  `server.js`. Endpoints the UI uses: `/api/search/identify`, `/api/search/image`,
  `/api/search/text`, `/api/users/*`, `/api/classify`, `/api/coupons`, `/health`.
- Image search uses **SerpAPI Google Lens** (httpx), NOT local CLIP/torch.
  `backend/app/embeddings.py` is dead code (nothing imports it); torch is not installed.
- Deploy loop: **git push → ansible deploy** (Terraform only for infra).

---

## Why "works on my PC" didn't work on Azure
Local gave for free what the VMs must be configured for:
- `localhost:8000` meant the local backend; in a browser on Azure it means the
  visitor's own machine → fixed by `VITE_API_BASE_URL=/api` + Nginx proxy.
- Local ran the FastAPI app; Azure was building the Node `server.js` → fixed by the
  FastAPI Dockerfile.
- Local had Postgres + SerpAPI key + CORS for localhost:5173 → now provisioned/passed.
- Local had no network boundary; backend VMs are private → reached via the public VM proxy.

---

## Changes made this session (FastAPI deployment)

### Backend
- `backend/Dockerfile` → FastAPI image: `python:3.11-slim`, installs `requirements.txt`,
  `COPY app/`, `CMD uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- `backend/app/main.py` → CORS now reads `CORS_ALLOW_ORIGINS` env (comma-separated),
  plus localhost defaults.

### Ansible
- `group_vars/backend.yaml` → port 8000, image env (`serpapi_key`, `apify_api_token`,
  `database_url`), Postgres container vars (`private-db`, `postgres:16`, db `priceapp`).
- `group_vars/frontend.yaml` → `vite_api_base_url=/api`, `backend_url` defaults to the
  first `[backend]` host's private IP:8000.
- `playbooks/deploy.yaml` → split into plays: clone+network, backend (Postgres →
  wait for pg_isready → build+run FastAPI on 8000), frontend (build with
  `VITE_API_BASE_URL`, run Nginx with `BACKEND_URL`), NFS mount.

### Frontend
- `frontend/Dockerfile` → build stage bakes `VITE_API_BASE_URL` (ARG), serve stage is
  `nginx:1.27-alpine` using `nginx.conf.template` (envsubst `${BACKEND_URL}` at start).
- `frontend/nginx.conf.template` → serves SPA on 3000, proxies `/api/` to `BACKEND_URL`.

### Terraform
- `main.tf` backend NSG: added `allow-app-from-frontend` for port **8000** from the
  frontend ASG (FastAPI port). (Old rule opened 3000; now 8000.)

---

## Deploy procedure

### 1. Apply infra change (new NSG 8000 rule)
```powershell
cd c:\gitrep2\buybot\terraform
terraform apply -var="admin_ip=YOUR.CURRENT.IP/32"
```

### 2. Commit + push app changes
```powershell
cd c:\gitrep2\buybot
git add backend/Dockerfile backend/app/main.py frontend/Dockerfile `
        frontend/nginx.conf.template ansible/ NOTES.md
git commit -m "feat: deploy FastAPI backend + Postgres + Nginx /api proxy"
git push origin dev
```

### 3. Deploy from the ansible master  (PERMANENT: always pulls latest from git)
The master runs playbooks from a git clone that it hard-syncs every time, so its
ansible files can NEVER go stale. Do NOT scp the ansible folder anymore.

First time only (bootstrap the script onto the master):
```bash
ssh azureuser@<ansible_master_ip>
git clone https://github.com/gswack/buybot.git ~/buybot   # if not already cloned
```

Every deploy after that (from the master):
```bash
# Backend: pass the ROTATED SerpAPI key (and Apify token if used)
bash ~/buybot/ansible/sync-and-deploy.sh dev backend \
  --extra-vars "serpapi_key=YOUR_ROTATED_SERPAPI_KEY apify_api_token=YOUR_APIFY_TOKEN"

# Frontend
bash ~/buybot/ansible/sync-and-deploy.sh dev frontend

# Everything
bash ~/buybot/ansible/sync-and-deploy.sh dev all --extra-vars "serpapi_key=..."
```
The script does: git fetch + checkout + `reset --hard origin/dev`, then runs
`ansible-playbook` from `~/buybot/ansible`. No manual copying.

IMPORTANT: `inventory.ini` is tracked in git. If `terraform apply` regenerates it
with new IPs, commit + push it so the master's sync picks it up.

### 4. Verify (backend health, then end-to-end)
```bash
# on master — containers up?
ansible backend -i inventory.ini -m shell -a "docker ps" --become
# FastAPI health (expect {"status":"ok"})
ansible backend -i inventory.ini -m shell -a "curl -s http://localhost:8000/health" --become
# backend logs (expect uvicorn running on 8000; no DB errors)
ansible backend -i inventory.ini -m shell -a "docker logs private-app --tail 30" --become
# real endpoint through the proxy, from the frontend VM:
ansible frontend -i inventory.ini -m shell -a "curl -s -X POST http://localhost:3000/api/search/text -F 'query=red dress' -F 'country_code=us'" --become
```
```powershell
# from laptop: open the UI and try text + image search
#   http://<public_vm_ip>:3000
```
Success = text/image search returns results in the UI (no "Failed to fetch").

---

## Open items / decisions
- [ ] **Rotate keys** (were public pre-history-rewrite): SerpAPI, Apify. Pass rotated
      SerpAPI key via `--extra-vars` at deploy; never commit.
- [ ] **Split-brain DB**: each backend VM runs its own Postgres. The Nginx proxy points
      at ONE backend, so only that VM's DB is used in practice. For real HA, use a single
      shared DB (managed Azure Postgres) and point all backends at it.
- [ ] Remove stray `backend/src/` hotels/Mongo app (unused, caused earlier confusion).
- [ ] Delete stray Node `backend/server.js` + `backend/routes/` prototype (superseded by FastAPI).
- [ ] Intermittent NIC race on `terraform apply` (`CanceledAndSupersededDueToAnotherOperation`).
      Re-run usually clears it; durable fix = `depends_on` so ASG assoc waits on NSG assoc.
- [ ] Master provisioner only runs on VM create. Push auto-provisioning to existing master:
      `terraform apply -replace="azurerm_linux_virtual_machine.ansible_master" -var="admin_ip=YOUR.IP/32"`.
- [ ] `terraform.tfvars` `admin_ip` must match current public IP or SSH/provisioner times out.
      Check: `(Invoke-WebRequest ifconfig.me/ip).Content.Trim()`.
- [ ] Backend VMs need **outbound internet** to reach SerpAPI. Public subnet has an
      Internet route; confirm the private subnet can egress (NAT/route) or image/text
      search will fail even with a healthy app.

## Cost control (overnight)
```powershell
az vm deallocate --ids $(az vm list -g RG --query "[].id" -o tsv)   # stop compute charges
az vm start      --ids $(az vm list -g RG --query "[].id" -o tsv)   # resume
```
NSGs are free. Full teardown = `terraform destroy` (loses IPs, full rebuild).

## Backup
Pre-rewrite repo backup: `c:\gitrep2\buybot-backup`
