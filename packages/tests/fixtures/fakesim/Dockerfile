# Lightweight stand-in for the DeepRacer sim (see server.py). Native to the host
# arch so it pulls/starts in seconds — the heavy amd64 sim is validated on PACE.
FROM python:3.12-slim
COPY server.py /server.py
ENV GYM_PORT=8888
ENTRYPOINT ["python", "/server.py"]
