FROM ubuntu:26.04@sha256:c098726dd9b9733f3e885f8de0ef375206a311b0a317eadc40d347b1115fb944
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends novnc websockify && rm -rf /var/lib/apt/lists/*
CMD ["websockify", "--web", "/usr/share/novnc", "6080", "inferno-local-restore:5900"]
