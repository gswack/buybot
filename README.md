# 🧠 AI Price Comparison Platform

> Find the cheapest online prices for products using AI-powered search, web scraping, and DevOps automation.

---

## 🚀 Overview

This project scans e-commerce websites for product prices, applies credit card discounts, and returns the cheapest total option — powered by FastAPI, React, and a cloud-native DevOps pipeline.

---

## 🧩 Features

- 🔍 AI-powered product search (semantic matching)
- 💰 Multi-site price aggregation
- 💳 Credit card discount integration
- 🧱 CI/CD pipeline with Docker + ArgoCD
- ☁️ Cloud deployment via Terraform on GKE

---

## 🧠 Architecture

![Architecture Diagram](docs/architecture-diagram.png)

---

## 🧰 Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | React, TailwindCSS |
| Backend | FastAPI, Python |
| AI / NLP | OpenAI embeddings, FuzzyWuzzy |
| Infra | Docker, Kubernetes, Terraform |
| CI/CD | GitHub Actions, ArgoCD |
| Monitoring | Prometheus, Grafana |
| Hosting | GCP (GKE) |

---

## ⚙️ Setup

### 1️⃣ Clone the repo
```bash
git clone https://github.com/gswack/buybot.git
cd buybot

### Install Dependencies (using poetry)
poetry install
poetry shell

Checks and Balances
A. Terraform
1. cd terraform
2. terraform init; terraform validate
3. terraform apply

B. Test Ansible
ssh into the ansible master VM:
1. ssh azureuser@<master public ip>
2. cd ansible (or cd ~/ansible)
3. ansible-inventory -i inventory.ini --list
4. ansible all -i inventory.ini -m ping

C. Install Docker + Git on the app VMs
ansible-playbook -i inventory.ini playbooks/install.yaml

D. Run Deploy
ansible-playbook -i inventory.ini playbooks/deploy.yaml

E. Stop VMs and resource groups:
az vm deallocate --ids $(az vm list -g RG --query "[].id" -o tsv)

F. Destroy
terraform destroy

Tests:
A. Ansible (from ansible master VM)
1. ansible backend -i inventory.ini -m shell -a "docker ps" --become
2. ansible backend -i inventory.ini -m shell -a "docker logs private-app --tail 50" --become

B. Listen on port 300 inside VM:
ansible backend -i inventory.ini -m shell -a "ss -tlnp" --become

C. API responds locally on the backend VM:
ansible backend -i inventory.ini -m shell -a "curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/" --become

D. ansible backend -i inventory.ini -m shell -a "curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/" --become

E. Frontend:
ansible frontend -i inventory.ini -m shell -a "curl -s -o /dev/null -w '%{http_code}' http://10.0.0.133:3000/" --become
ansible frontend -i inventory.ini -m shell -a "curl -s -o /dev/null -w '%{http_code}' http://10.0.0.132:3000/" --become

7. Frontend pointing at the backend:
ansible frontend -i inventory.ini -m shell -a "docker logs public-app --tail 30" --become

8. Upstream dependency reachable:
ansible backend -i inventory.ini -m shell -a "curl -s -o /dev/null -w '%{http_code}' https://api.priceapi.com" --become

9. Sanity check (from host PC)
az network nsg rule list --nsg-name backendSecurityGroup --resource-group RG -o table
