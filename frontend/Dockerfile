# Stage 1: install deps and build. Needs the full node_modules tree
# (including devDependencies like typescript/tailwind) that the final
# image never needs to ship.
FROM node:20-slim AS builder
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# Baked in at build time since Next.js inlines NEXT_PUBLIC_* values into
# the client bundle — it can't be swapped at container-start time the
# way a server-side env var can. Override via --build-arg for a
# different backend URL per environment.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN npm run build

# Stage 2: the actual runtime image — just the standalone server Next.js
# traced out in stage 1, not the full node_modules or source tree.
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production

RUN useradd --create-home appuser
COPY --from=builder /app/public ./public
COPY --from=builder --chown=appuser:appuser /app/.next/standalone ./
COPY --from=builder --chown=appuser:appuser /app/.next/static ./.next/static

USER appuser
EXPOSE 3000
CMD ["node", "server.js"]
