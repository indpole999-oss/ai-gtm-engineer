FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1
COPY probe.py /opt/recovery/probe.py
USER 65534:65534
ENTRYPOINT ["python", "/opt/recovery/probe.py", "--idle"]
CMD []
