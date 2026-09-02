# 🧠 AI Price Comparison Platform - In Progress

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
poetry shel
```