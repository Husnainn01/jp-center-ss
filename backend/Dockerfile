FROM node:22-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npx prisma generate && npm run build

CMD ["node", "dist/index.js"]
