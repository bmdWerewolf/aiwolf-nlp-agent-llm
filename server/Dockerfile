# 1. Use a lightweight Linux base image
FROM debian:bookworm-slim

# 2. Install curl (for downloading)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# 3. Set working directory
WORKDIR /app

# 4. [Key] Download server binary during image build (not copied from local)
RUN curl -LO https://github.com/aiwolfdial/aiwolf-nlp-server/releases/latest/download/aiwolf-nlp-server-linux-amd64
RUN chmod u+x ./aiwolf-nlp-server-linux-amd64

# 5. Copy config files from build context (./server) to image
COPY default_5.yml .
COPY default_13.yml .
# COPY .env .

# 6. Set default startup command
CMD ["./aiwolf-nlp-server-linux-amd64", "-c", "./default_5.yml"]
