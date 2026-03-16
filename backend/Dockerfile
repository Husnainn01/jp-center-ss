FROM node:22-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npx prisma generate && npm run build

CMD ["sh", "-c", "node prisma/init-db.mjs && node dist/index.js"]
