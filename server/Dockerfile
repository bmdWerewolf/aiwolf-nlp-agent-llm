# 1. Use a lightweight Linux base image
FROM debian:bookworm-slim

# 2. Install curl (for downloading)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# 3. Set working directory
WORKDIR /app

# 4. [Key] Download server binary during image build (not copied from local)
RUN curl -LO https://github.com/aiwolfdial/aiwolf-nlp-server/releases/latest/download/aiwolf-nlp-server-linux-amd64
RUN chmod u+x ./aiwolf-nlp-server-linux-amd64

# 5. Config files will be mounted at runtime (not copied during build)
# This allows config changes without rebuilding the image

# 6. Set default startup command
# Config file path should match the mounted volume
CMD ["./aiwolf-nlp-server-linux-amd64", "-c", "./config/default_5_2Teams.yml"]
