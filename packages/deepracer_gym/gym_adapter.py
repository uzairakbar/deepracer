import zmq
import numpy as np

from deepracer_gym.zmq_client import DeepracerClientZMQ
from deepracer_gym.utils import (
    RewardParam, terminated_check, truncated_check
)


PORT: int=8888
HOST: str='127.0.0.1'
TIMEOUT_LONG: int=600_000   # 10m
TIMEOUT_SHORT: int=20_000   # 20s
DUMMY_ACTION: int=4


class DeepracerGymAdapter:
    def __init__(self, host: str=HOST, port: int=PORT):
        self.zmq_client = DeepracerClientZMQ(host=host, port=port)
        self.zmq_client.ready()
        self.response = None

    def _send_action(self, action: int):
        action: dict[str, int] = {'action': action}
        self.response = self.zmq_client.send_message(action)
        return self.response
    
    def env_reset(self):
        if self.response is None:
            # First communication to zmq server
            self.response = self.zmq_client.recieve_response()
            # Smaller timeout after first connection
            self.zmq_client.socket.set(zmq.SNDTIMEO, TIMEOUT_SHORT)
            self.zmq_client.socket.set(zmq.RCVTIMEO, TIMEOUT_SHORT)
        else:
            # If prev_episode done and reset called, fast forward one step for new episode
            # Action ignored due to reset()
            self.response = self._send_action_get_response(DUMMY_ACTION)
        
        if not isinstance(self.response['info'], dict):
            self.response['info'] = dict()
        self.response['info']['reward_params'] = RewardParam.make_default_param()
        observation, _, _, _, info = self._parse_response(self.response)
        return observation, info
    
    def send_action(self, action: int):
        action: dict[str, int] = {'action': action}
        self.response = self.zmq_client.send_message(action)
        return self._parse_response(self.response)
    
    @staticmethod
    def _parse_response(response: dict):
        info = response['info']
        if not isinstance(info, dict):
            info = dict()
        info['goal'] = response['_goal']

        game_over = response['_game_over']
        terminated = terminated_check(info['reward_params'], game_over)
        truncated = truncated_check(info['reward_params'], game_over)
        
        reward = response['_reward']
        observation = response['_next_state']
        # channel first convention
        observation = {
            sensor: (
                measurement.transpose(-1, 0, 1) if 'CAMERA' in sensor
                else measurement
            ) for sensor, measurement in observation.items()
        }
        return observation, reward, terminated, truncated, info
