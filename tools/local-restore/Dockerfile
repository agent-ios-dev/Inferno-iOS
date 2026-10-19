FROM ubuntu:26.04@sha256:c098726dd9b9733f3e885f8de0ef375206a311b0a317eadc40d347b1115fb944
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git build-essential autoconf automake libtool-bin \
    pkg-config meson ninja-build cmake python3 python3-pyasn1 python3-pyasn1-modules \
    python3-cryptography python3-requests python3-packaging \
    libglib2.0-dev libpixman-1-dev zlib1g-dev liblzfse-dev liblz4-dev nettle-dev libgmp-dev \
    libgnutls28-dev libslirp-dev libpng-dev libzstd-dev libusb-1.0-0-dev \
    libssl-dev libcurl4-openssl-dev libzip-dev libreadline-dev libxml2-dev \
    libplist-dev libimobiledevice-glue-dev libusbmuxd-dev libimobiledevice-dev \
    libtatsu-dev \
    && rm -rf /var/lib/apt/lists/*
COPY core.tar /tmp/core.tar
RUN mkdir -p /opt/inferno/src && tar -xf /tmp/core.tar -C /opt/inferno/src \
    && rm /tmp/core.tar \
    && python3 -c "from pathlib import Path; [(p.write_bytes(p.read_bytes().replace(b'\r\n', b'\n'))) for p in Path('/opt/inferno/src').rglob('*') if p.is_file() and p.open('rb').read(2) == b'#!']" \
    && meson setup /opt/inferno/build /opt/inferno/src \
       -Dbuildtype=debugoptimized -Dwerror=false -Dshared_lib=false \
       -Dkvm=disabled -Dhvf=disabled -Dwhpx=disabled \
       -Dgtk=disabled -Dsdl=disabled -Dcocoa=disabled -Dcurses=disabled \
       -Dcurl=disabled -Dlibssh=disabled -Dvnc=enabled -Dvnc_jpeg=disabled \
       -Dvnc_sasl=disabled -Dtools=enabled \
    && ninja -C /opt/inferno/build -j4
COPY idevicerestore.patch /tmp/idevicerestore.patch
RUN git clone --depth 1 https://github.com/libimobiledevice/libirecovery /opt/libirecovery \
    && cd /opt/libirecovery && ./autogen.sh && make -j4 && make install && ldconfig \
    && git rev-parse HEAD > /opt/libirecovery-revision
RUN git clone --depth 1 https://github.com/libimobiledevice/idevicerestore /opt/idevicerestore \
    && cd /opt/idevicerestore && test "$(git rev-parse HEAD)" = 4b3e847e1d9a1210049a9e3f1d1caa38650c6617 \
    && python3 -c "from pathlib import Path; p=Path('/tmp/idevicerestore.patch'); p.write_bytes(p.read_bytes().replace(b'\r\n', b'\n'))" \
    && git apply /tmp/idevicerestore.patch \
    && ./autogen.sh && make -j4 && make install && ldconfig \
    && git rev-parse HEAD > /opt/idevicerestore-revision
RUN git clone --depth 1 https://github.com/xerub/img4lib /opt/img4lib \
    && make -C /opt/img4lib -j4 \
    && git -C /opt/img4lib rev-parse HEAD > /opt/img4lib-revision
ENV PATH="/opt/inferno/build:/opt/img4lib:/usr/local/bin:${PATH}"
WORKDIR /vm
CMD ["bash"]
