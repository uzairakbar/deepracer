from enum import Enum
from loguru import logger


class RewardParam(Enum):
    WHEELS_ON_TRACK = ['all_wheels_on_track', True]
    X = ['x', 0.0]                                                      # float: race car x position
    Y = ['y', 0.0]                                                      # float: race car y position
    HEADING = ['heading', 0.0]                                          # float: race car heading angle
    CENTER_DIST = ['distance_from_center', 0.0]                         # float: race car distance from centerline
    PROJECTION_DISTANCE = ['projection_distance', 0.0]                  # float: race car distance projected on the centerline
    PROG = ['progress', 0.0]                                            # float: race car track progress [0,1]
    STEPS = ['steps', 0]                                                # int: number of steps race car have taken
    SPEED = ['speed', 0.0]                                              # float: race car speed
    STEER = ['steering_angle', 0.0]                                     # float: race car steering angle
    TRACK_WIDTH = ['track_width', 0.0]                                  # float: track width
    TRACK_LEN = ['track_length', 0.0]                                   # float: track length
    WAYPNTS = ['waypoints', 0]                                          # list of tuple: list of waypoints (x, y) tuple
    CLS_WAYPNY = ['closest_waypoints', [0, 0]]                          # list of int: list of int with size 2 containing closest prev and next waypoint indexes
    LEFT_CENT = ['is_left_of_center', False]                            # boolean: race car left of centerline
    REVERSE = ['is_reversed', False]                                    # boolean: race car direction
    CLOSEST_OBJECTS = ['closest_objects', [0, 0]]                       # list of int: list of int with size 2 containing closest prev and next object indexes
    OBJECT_LOCATIONS = ['objects_location', []]                         # list of tuple: list of all object (x, y) locations
    OBJECTS_LEFT_OF_CENTER = ['objects_left_of_center', []]             # list of boolean: list of all object to the left of centerline or not
    OBJECT_IN_CAMERA = ['object_in_camera', False]                      # boolean: any object in camera
    OBJECT_SPEEDS = ['objects_speed', []]                               # list of float: list of objects speed
    OBJECT_HEADINGS = ['objects_heading', []]                           # list of float: list of objects heading
    OBJECT_CENTER_DISTS = ['objects_distance_from_center', []]          # list of float: list of object distance from centerline
    OBJECT_CENTERLINE_PROJECTION_DISTANCES = ['objects_distance', []]   # list of float: list of object distance projected on the centerline
    CRASHED = ['is_crashed', False]                                     # boolean: crashed into an object or bot car
    OFFTRACK = ['is_offtrack', False]

    @classmethod
    def make_default_param(cls):
        '''Returns a dictionary with the default values for the reward function'''
        return {key.value[0] : key.value[-1] for key in cls}


def terminated_check(episode_status: dict, game_over: bool):
    if game_over and (
        episode_status['lap_complete']
        or
        episode_status['crashed']
        or
        episode_status['reversed']
        or
        episode_status['off_track']
    ):
        return True
    return False


def truncated_check(episode_status: dict, game_over: bool):
    terminated = terminated_check(episode_status, game_over)
    # time_out or immobilized
    truncated = (game_over and not terminated)
    if truncated:
        status = [k for k, v in episode_status.items() if v]
        if not episode_status['immobilized'] and not episode_status['time_up']:
            logger.warning(
                f'Expected immibilized or time_up status for truncated episode.'
                f'Instead got {status}.'
                f'Restart deepracer to prevent unexpected behavior.'
            )
    return truncated
