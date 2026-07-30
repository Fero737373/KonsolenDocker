FROM debian:trixie-slim AS pegasus-builder

ARG PEGASUS_REF=6b322063a036db60cba5810fda82a3ce38f1e62f

RUN sed -i 's/Components: main/Components: main contrib non-free non-free-firmware/' \
        /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        cmake \
        git \
        libqt5gamepad5-dev \
        libqt5svg5-dev \
        libsdl2-dev \
        ninja-build \
        pkg-config \
        qtbase5-dev \
        qtdeclarative5-dev \
        qtmultimedia5-dev \
        qttools5-dev \
        qttools5-dev-tools \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --filter=blob:none https://github.com/mmatyas/pegasus-frontend.git /src/pegasus \
    && git -C /src/pegasus checkout "${PEGASUS_REF}" \
    && git -C /src/pegasus submodule update --init --recursive --depth 1

RUN cmake \
        -S /src/pegasus \
        -B /build/pegasus \
        -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DPEGASUS_ENABLE_LTO=OFF \
    && cmake --build /build/pegasus --target pegasus-fe --parallel \
    && DESTDIR=/stage cmake --install /build/pegasus


FROM debian:trixie-slim AS pcsx-builder

ARG PCSX_REARMED_REF=94f15b3a6b707070aeb0c58cab9bc4eddc1706ff

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --filter=blob:none https://github.com/libretro/pcsx_rearmed.git /src/pcsx_rearmed \
    && git -C /src/pcsx_rearmed checkout "${PCSX_REARMED_REF}" \
    && make -C /src/pcsx_rearmed -f Makefile.libretro platform=unix -j"$(nproc)" \
    && install -Dm755 /src/pcsx_rearmed/pcsx_rearmed_libretro.so \
        /stage/usr/local/lib/libretro/pcsx_rearmed_libretro.so


FROM debian:trixie-slim

LABEL org.opencontainers.image.source="https://github.com/Fero737373/KonsolenDocker"
LABEL org.opencontainers.image.description="Pegasus and classic emulators for Raspberry Pi 5"

RUN sed -i 's/Components: main/Components: main contrib non-free non-free-firmware/' \
        /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        fontconfig \
        gstreamer1.0-alsa \
        gstreamer1.0-libav \
        gstreamer1.0-plugins-base \
        gstreamer1.0-plugins-good \
        libgl1 \
        libgl1-mesa-dri \
        libqt5gamepad5 \
        libqt5multimedia5-plugins \
        libqt5svg5 \
        libretro-gambatte \
        libretro-genesisplusgx \
        libretro-mgba \
        libretro-nestopia \
        libretro-snes9x \
        libxkbcommon-x11-0 \
        libzstd1 \
        mame \
        mednafen \
        qml-module-qt-labs-folderlistmodel \
        qml-module-qt-labs-qmlmodels \
        qml-module-qt-labs-settings \
        qml-module-qtgraphicaleffects \
        qml-module-qtmultimedia \
        qml-module-qtqml-models2 \
        qml-module-qtquick-controls2 \
        qml-module-qtquick-layouts \
        qml-module-qtquick-particles2 \
        qml-module-qtquick-shapes \
        qml-module-qtquick-window2 \
        qml-module-qtquick2 \
        retroarch \
        stella \
    && rm -rf /var/lib/apt/lists/*

COPY --from=pegasus-builder /stage/ /
COPY --from=pcsx-builder /stage/ /
COPY docker/entrypoint.sh /usr/local/bin/konsolen-entrypoint
COPY docker/launch-* /usr/local/bin/
COPY docker/retroarch.cfg /opt/konsolen/retroarch.cfg

ENV PATH=/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games \
    HOME=/games/config/runtime-home \
    XDG_CACHE_HOME=/games/cache \
    XDG_CONFIG_HOME=/games/config \
    XDG_DATA_HOME=/games/config/share \
    QT_QPA_PLATFORM=xcb \
    SDL_VIDEODRIVER=x11 \
    SDL_AUDIODRIVER=alsa

ENTRYPOINT ["/usr/local/bin/konsolen-entrypoint"]
