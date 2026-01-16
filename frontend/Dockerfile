FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json /app/
RUN npm ci

COPY . /app

# Build-time public env for client bundle (defaults to localhost backend)
ARG NEXT_PUBLIC_API_BASE=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}

RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start", "--", "-p", "3000"]

