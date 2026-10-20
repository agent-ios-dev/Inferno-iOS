FROM inferno-local:sep-status
RUN apt-get update && apt-get install -y --no-install-recommends libgtk-3-dev libepoxy-dev \
    && rm -rf /var/lib/apt/lists/* \
    && meson configure /opt/inferno/build -Dgtk=enabled \
    && ninja -C /opt/inferno/build -j4 qemu-system-aarch64
ENV GDK_BACKEND=x11 DISPLAY=:0
