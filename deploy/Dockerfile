FROM node:20-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 ffmpeg bash ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . /app
RUN cd bridge && npm install --omit=optional --no-audit --no-fund
ENV HOST=127.0.0.1
CMD ["bash", "start.sh"]
