FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y curl ca-certificates libssl3 python3 python3-pip && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://github.com/block/goose/releases/latest/download/goose-x86_64-unknown-linux-gnu.tar.gz | tar -xz -C /usr/local/bin/ && chmod +x /usr/local/bin/goose
RUN pip3 install python-telegram-bot requests --break-system-packages
COPY config.yaml /root/.config/goose/config.yaml
COPY bot.py .
EXPOSE 3000
CMD bash -c "goose server --port 3000 --host 0.0.0.0 & python3 bot.py"
