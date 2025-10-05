FROM node:22-alpine

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

# Build production bundle
RUN npm run build

# Serve using Vite preview
EXPOSE 4173
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0"]
