import zmq
import msgpack
import msgpack_numpy as m
from rl_coach.core_types import ActionInfo
from rl_coach.agents.clipped_ppo_agent import ClippedPPOAgent


m.patch()
DUMMY_ACTION: int=0


class Server:
    def __init__(self, host='0.0.0.0', port=8888):
        self.host = host
        self.port = port
        self.socket = zmq.Context.instance().socket(zmq.REP)
        self.socket.set(zmq.SNDTIMEO, 5000)
        self.socket.bind(f'tcp://{self.host}:{self.port}')

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.socket.close()

    def run(self):
        print('Starting server...')
        while True:
            packed_msg = self.socket.recv()
            msg = msgpack.unpackb(packed_msg)

            print('Received a message')
            print(msg)

            response = {'success': True}
            packed_response = msgpack.packb(response)
            self.socket.send(packed_response)


class GymAgent(ClippedPPOAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.server = Server()
        self._previous_done = False
        self._hard_reset = False
        self._recieved_message = None
        print(f'================= Waiting for gym client =================')

        packed_msg = self.server.socket.recv()
        msg = msgpack.unpackb(packed_msg)
        print(f'=================== Gym Client Ready! ===================')

    def observe(self, env_response):
        response_dict = env_response.__dict__
        self._previous_done = response_dict['_game_over']
        if not self._hard_reset:
            packed_response = msgpack.packb(response_dict)
            self.server.socket.send(packed_response)

            packed_msg = self.server.socket.recv()
            self._recieved_message = msgpack.unpackb(packed_msg)
        else:
            self._recieved_message = {}
            if self._previous_done:
                self._hard_reset = False
                self._recieved_message['action'] = DUMMY_ACTION  # IGNORED DUE TO RESET
    
    def act(self):
        if not self._hard_reset:

            if (self._recieved_message.get('action') is not None):
                action = self._recieved_message['action']

            elif (self._recieved_message.get('ready') is not None):
                self._hard_reset = True
                action = DUMMY_ACTION

        else:
            action = DUMMY_ACTION
        return ActionInfo(action=action)
