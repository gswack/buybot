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

