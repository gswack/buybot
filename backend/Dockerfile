FROM node:22-slim
WORKDIR /app

# Install dependencies. server.js and routes/search.js require express, cors,
# dotenv and axios. dotenv/axios are not yet in package.json, so install
# explicitly to guarantee they are present in the image.
COPY package*.json ./
RUN npm install --omit=dev \
    && npm install --omit=dev axios dotenv

# Copy the price-comparison API (NOT src/, which is a separate hotels/Mongo app)
COPY server.js ./server.js
COPY routes/ ./routes/

# The app listens on process.env.PORT || 3000; deploy maps 3000:3000.
EXPOSE 3000
CMD ["node", "server.js"]
