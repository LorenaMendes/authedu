FROM node:26.13.0-bookworm-slim

WORKDIR /app

RUN npm install --global npm@12.2.1

COPY package.json package-lock.json .npmrc ./
RUN npm ci

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
