import zmq
import time
import msgpack

import msgpack_numpy as m
m.patch()


PORT: int=8888
HOST: str='127.0.0.1'
TIMEOUT_LONG: int=600_0000  # 10m
TIMEOUT_SHORT: int=200_000  # 20s


class DeepracerClientZMQ:
    def __init__(self, host: str=HOST, port: int=PORT):
        self.host = host
        self.port = port
        self.socket = zmq.Context().socket(zmq.REQ)

        # Large timout for first connection
        self.socket.set(zmq.SNDTIMEO, TIMEOUT_LONG)
        self.socket.set(zmq.RCVTIMEO, TIMEOUT_LONG)

        self.socket.connect(f'tcp://{self.host}:{self.port}')
    
    def ready(self):
        message: dict[str, int] = {'ready': 1}
        self._send_message(message)

    def recieve_response(self):
        packed_response = self.socket.recv()
        response = msgpack.unpackb(packed_response)
        return response

    def send_message(self, message: dict[str, int]):
        self._send_message(message)
        response = self.recieve_response()
        return response
    
    def _send_message(self, message: dict[str, int]):
        packed_message = msgpack.packb(message)
        self.socket.send(packed_message)
