FROM python:3.13-slim-trixie

LABEL org.opencontainers.image.source="https://github.com/Fero737373/KonsolenDocker"
LABEL org.opencontainers.image.description="Restricted legal-homebrew downloader for Pegasus"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/konsolendocker

WORKDIR /opt/konsolendocker
COPY romstore /opt/konsolendocker/romstore

ENTRYPOINT ["python", "-m", "romstore"]
