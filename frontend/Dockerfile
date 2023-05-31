FROM node:16-alpine3.17

WORKDIR /loop

COPY package.json frontend/package.json

COPY pnpm-lock.yaml frontend/pnpm-lock.yaml

RUN npm install -g pnpm

RUN pnpm install --prefix frontend

COPY . frontend/

WORKDIR /loop/frontend

RUN pnpm run build

RUN npm install -g serve

CMD ["serve", "-s", "dist", "-l", "3000"]



