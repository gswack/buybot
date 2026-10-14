# BuyBot — Session Notes

Working notes for the Azure deployment of the price-comparison app
(frontend on public VM, backend on private VMs, Ansible master as jump box).

---

## Architecture (quick reminder)

- **public-vm** (public subnet, public IP) → **frontend** (Vite/React), reachable from internet on `:3000`.
- **private-vm-1 / private-vm-2** (private subnet, no public IP) → **backend** PriceAPI (`server.js`, `:3000`).
- **ansible-master** (public subnet, public IP) → jump box; runs playbooks over the VNet.
- Flow: Internet → public-vm:3000 → private-vm:3000. NSGs: frontend allows 3000 from `*`; backend allows 3000 only from the frontend ASG.

Deploy loop is **git push → ansible deploy** (Terraform only for infra).

---

## Major fixes made this session

### Terraform (`terraform/main.tf`)
1. Fixed broken inventory reference `azurerm_public_ip.private_vm_ip` (did not exist). Frontend host now uses its **private** IP (public IPs break VNet/ASG routing).
2. Inventory now VNet-reachable: `ansible-master` uses `ansible_connection=local` instead of SSHing to its own public IP (NSG blocks that).
3. Master auto-provisioning: added `connection` + `file` provisioners to copy the `ansible/` folder AND the private SSH key to the master, plus `remote-exec` to `chmod 600` the key. Removes manual `scp`.

### Git / secrets
4. Purged secrets from git history with `git filter-repo` — removed `backend/.env` from every commit and redacted the hardcoded PriceAPI token. Force-pushed cleaned `dev` and `master`. Backup at `c:\gitrep2\buybot-backup`.
5. `routes/search.js` now reads `process.env.PRICEAPI_TOKEN`; `.gitignore` excludes all `.env` files; `backend/.env` untracked.

### Application / Docker
6. Created `frontend/Dockerfile` (multi-stage Vite build, served on 3000, bound to 0.0.0.0). Previously missing → "Cannot locate specified Dockerfile".
7. Rewrote `backend/Dockerfile`: it was running `src/server.js` (a SEPARATE hotels/MongoDB app needing a Vault secret → `Vault secret not found` crash loop). Now runs the real PriceAPI `server.js` on 3000, copies `routes/`, installs missing `axios` + `dotenv`.
8. `ansible/playbooks/deploy.yaml` now passes `PRICEAPI_TOKEN` to the backend container via the `priceapi_token` Ansible var (value not committed).

---

## TODO — pick up here tomorrow

### 1. Rotate exposed keys (SECURITY — do first)
The following were public on GitHub before the history rewrite. Treat as compromised; regenerate:
- [ ] SerpAPI key
- [ ] Apify API token
- [ ] PriceAPI token

### 2. Commit + push the app fixes
```powershell
cd c:\gitrep2\buybot
git add frontend/Dockerfile backend/Dockerfile ansible/playbooks/deploy.yaml NOTES.md
git commit -m "fix: frontend+backend Dockerfiles, pass PRICEAPI_TOKEN to backend"
git push origin dev
```

### 3. Redeploy (from the ansible master)
```bash
cd ~/ansible
# frontend
ansible-playbook -i inventory.ini playbooks/deploy.yaml --limit frontend -vv
# backend (pass the ROTATED token at runtime)
ansible-playbook -i inventory.ini playbooks/deploy.yaml --limit backend \
  --extra-vars "priceapi_token=YOUR_ROTATED_TOKEN"
```

### 4. Verify
```bash
# on master
ansible frontend:backend -i inventory.ini -m shell -a "docker ps" --become
ansible backend -i inventory.ini -m shell -a "docker logs private-app --tail 20" --become
```
Want: containers `Up` (not `Restarting`); backend log shows `Server running on port 3000`.
```powershell
# from laptop
curl http://<public_vm_ip>:3000
curl "http://<public_vm_ip>:3000/api/search?query=laptop&cardType=visa"
```
The `/api/search` JSON array = full price-comparison app working end-to-end.

### 5. Open items / decisions
- [ ] Decide whether to delete the stray `backend/src/` hotels/Mongo app so it can't get built again.
- [ ] Intermittent NIC race on `terraform apply` (`CanceledAndSupersededDueToAnotherOperation`). Re-run usually clears it; durable fix = add `depends_on` so the ASG association waits on the NSG association for each NIC (master + public).
- [ ] Master provisioner only runs on VM create. To push the auto-provisioning to the existing master: `terraform apply -replace="azurerm_linux_virtual_machine.ansible_master" -var="admin_ip=YOUR.IP/32"`.
- [ ] `terraform.tfvars` `admin_ip` must match current public IP or SSH/provisioner times out. Check: `(Invoke-WebRequest ifconfig.me/ip).Content.Trim()`.
- [ ] "Failed to fetch" in UI: re-check after backend is healthy; if it persists, verify frontend's API URL target and backend outbound egress to `api.priceapi.com`.

### Cost control (overnight)
Deallocate (keeps infra, stops compute charge):
```powershell
az vm deallocate --ids $(az vm list -g RG --query "[].id" -o tsv)
# start again:
az vm start --ids $(az vm list -g RG --query "[].id" -o tsv)
```
NSGs/security groups are free. Full teardown = `terraform destroy` (loses IPs, needs full rebuild).

### Backup
Pre-rewrite repo backup: `c:\gitrep2\buybot-backup`
