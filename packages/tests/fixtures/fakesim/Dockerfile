# Lightweight ZMQ stand-in for the DeepRacer sim (see server.py). Native to the
# host arch so it builds/starts in seconds — the heavy amd64 sim is validated on
# PACE. Speaks the same REQ/REP msgpack protocol the client expects.
FROM python:3.12-slim
RUN pip install --no-cache-dir pyzmq numpy msgpack msgpack_numpy
COPY server.py /server.py
ENV GYM_PORT=8888
ENTRYPOINT ["python", "/server.py"]
