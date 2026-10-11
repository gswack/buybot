# Hotel Booking Backend API

## Commands 
1. docker start buybot-postgres
2. docker run -d --name buybot-postgres -e POSTGRES_PASSWORD=yourpassword -e POSTGRES_DB=buybot -p 5432:5432 pgvector/pgvector:pg16
3. docker exec -it buybot-postgres psql -U postgres -d priceapp -c "CREATE EXTENSION IF NOT EXISTS vector;"
4. docker start buybot-postgres
5. source .venv/Scripts/activate
6. uvicorn app.main:app --reload

02b7ebe7d93c85c1c8a07732a0bcf20df6e682d34e584274162177465793c477

Backend service for the Hotel Booking platform.

This application provides RESTful APIs for managing hotels and reservations. It is built with Node.js and Express and uses MongoDB for persistent data storage.

The backend is containerized with Docker and deployed on Kubernetes using ArgoCD GitOps automation.

---

## Technology Stack

* Node.js 18
* Express.js
* MongoDB
* Mongoose ODM
* Docker
* Kubernetes
* ArgoCD
* Nexus Docker Registry
* Grafana / Loki monitoring stack

---

# Application Features

The backend provides:

* Retrieve available hotels
* Create new reservations
* Search reservations by customer information
* Cancel existing reservations
* Store reservation data in MongoDB

---

# Project Structure

```
backend-repo/
│
├── src/
│   ├── server.js
│   │
│   ├── routes/
│   │   ├── hotels.js
│   │   └── reservations.js
│   │
│   ├── models/
│   │   └── Reservation.js
│   │
│   └── data/
│       └── hotels.json
│
├── Dockerfile
├── package.json
├── package-lock.json
└── README.md
```

---

# API Endpoints

## Hotels

### Get all hotels

```
GET /hotels
```

Example response:

```json
[
  {
    "id": 1,
    "name": "Hilton",
    "location": "San Diego, CA",
    "price_per_night": 120
  }
]
```

---

## Reservations

### Create reservation

```
POST /reservations
```

Request body:

```json
{
  "hotelId": 1,
  "fullName": "John Smith",
  "email": "john@example.com",
  "checkIn": "2026-07-25",
  "checkOut": "2026-07-30"
}
```

Response:

```json
{
  "message": "Reservation created successfully"
}
```

---

### Lookup reservation

```
GET /reservations/lookup?query=email@example.com
```

---

### Cancel reservation

```
DELETE /reservations/:id
```

---

# Environment Configuration

The application uses environment variables for configuration.

Example:

```env
MONGO_URL=mongodb://mongodb.hotel-backend.svc.cluster.local:27017/hotelapp
PORT=3000
NODE_ENV=production
```

The environment variables are injected into Kubernetes using ConfigMaps and Secrets.

---

# Running Locally

## Install dependencies

```bash
npm install
```

## Start application

```bash
npm start
```

The API will run on:

```
http://localhost:3000
```

---

# Docker

## Build Docker image

```bash
docker build -t backend:v1 .
```

## Run locally

```bash
docker run -p 3000:3000 backend:v1
```

Test:

```bash
curl http://localhost:3000/hotels
```

---

# Docker Registry

Docker images are stored in the Nexus private registry.

Example image:

```
172.18.0.4:30082/backend:v3
```

Image versions are managed using tags:

```
backend:v1
backend:v2
backend:v3
```

Each deployment references a specific image version.

---

# Kubernetes Deployment

The backend is deployed into Kubernetes namespace:

```
hotel-backend
```

Kubernetes resources:

* Deployment
* Service
* ConfigMap
* Secret
* Persistent storage for MongoDB
```

Verify:

```bash
kubectl get pods -n hotel-backend
```

Example:

```
backend-xxxxx   Running
mongodb-xxxxx   Running
```

---

# CI/CD Pipeline

The backend deployment process:

```
Developer
    |
    v
GitHub Repository
    |
    v
GitHub Actions
    |
    v
Docker Build
    |
    v
Push Image to Nexus
    |
    v
Update Kubernetes Manifest
    |
    v
ArgoCD Synchronization
    |
    v
Kubernetes Deployment
```

---

# GitOps Deployment with ArgoCD

ArgoCD continuously monitors the Kubernetes manifests.

When changes are merged into the MAIN branch:

1. ArgoCD detects repository changes
2. Kubernetes manifests are synchronized
3. New backend pods are deployed
4. Previous versions are replaced

---

# Database

MongoDB stores reservation information.

The backend connects using:

```
mongodb://mongodb.hotel-backend.svc.cluster.local:27017/hotelapp
```

Reservation data is persisted in MongoDB collections.

Example collection:

```
reservations
```

---

# Monitoring

The backend is monitored using:

* Prometheus
* Loki
* Grafana
* Promtail

Collected information:

* Backend container logs
* MongoDB logs
* Kubernetes metrics

Example Loki query:

```
{namespace="hotel-backend"}
```

---

# Health Verification

Check backend pods:

```bash
kubectl get pods -n hotel-backend
```

Check logs:

```bash
kubectl logs deployment/backend -n hotel-backend
```

Test API:

```bash
curl http://localhost:3000/hotels
```

---

# Author

Gabriel Swack

