import torch
import torch.nn as nn
from math import prod
from deepracer_gym.envs.utils import (
    # use these dimensions if required
    LIDAR_SHAPE,
    STEREO_CAMERA_SHAPE,
    FRONT_FACING_CAMERA_SHAPE
)


LIDAR_FLATTEN_SHAPE: int=prod(LIDAR_SHAPE)
STEREO_FLATTEN_CAMERA_SHAPE: int=prod(STEREO_CAMERA_SHAPE)
FRONT_FLATTEN_FACING_CAMERA_SHAPE: int=prod(FRONT_FACING_CAMERA_SHAPE)


class UnflattenObservation(nn.Module):
    '''
    Use this class for un-flattening your observations if needed.
    '''
    def forward(self, x):
        # # trailing values are LiDAR
        # return (
        #     x[..., :-LIDAR_FLATTEN_SHAPE].view(-1, *STEREO_CAMERA_SHAPE),
        #     x[..., -LIDAR_FLATTEN_SHAPE:].view(-1, *LIDAR_SHAPE)
        # )
        # leading values are LiDAR
        return (
            x[..., LIDAR_FLATTEN_SHAPE:].view(-1, *STEREO_CAMERA_SHAPE),    # camera shape is (2, 120, 160)
            x[..., :LIDAR_FLATTEN_SHAPE].view(-1, *LIDAR_SHAPE)             # lidar shape is (64,)
        )


class EncodeObservation(nn.Module):
    '''
    Use this class to aggregate all of your observation
    pre-processing and encoding functions if required.
    '''
    def __init__(self):
        super().__init__()
        self.unflatten = UnflattenObservation()

        # put anything else that you require...
        raise NotImplementedError
    
    def forward(self, x):
        # get original dimensions for the observations
        camera, lidar = self.unflatten(x)

        # put anything else that you require...
        raise NotImplementedError
        
