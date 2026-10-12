# ---- Build stage ----
FROM node:22-slim AS build
WORKDIR /app

# Install dependencies (use lockfile for reproducible builds)
COPY package*.json ./
RUN npm ci

# Build the Vite app into /app/dist
COPY . .
RUN npm run build

# ---- Serve stage ----
FROM node:22-slim AS serve
WORKDIR /app

# Lightweight static file server
RUN npm install -g serve

# Copy only the built assets from the build stage
COPY --from=build /app/dist ./dist

# The deploy maps host 3000 -> container 3000, and the NSG opens 3000.
# Bind to 0.0.0.0 so the port mapping is reachable from outside the container.
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]
