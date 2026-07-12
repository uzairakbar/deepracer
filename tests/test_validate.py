import json

import pytest

from deepracer.service.validate import (
    validate_configs, known_tracks, effective_world,
)
from deepracer.service.spec import spec_to_env, SimSpec
from deepracer.service.identity import make_identity


DISCRETE_AGENT = {
    'action_space': [
        {'steering_angle': 30, 'speed': 0.6},
        {'steering_angle': -30, 'speed': 0.6},
    ],
    'sensor': ['STEREO_CAMERAS', 'LIDAR'],
    'action_space_type': 'discrete',
    'version': '6',
}
GOOD_TRACK = {'WORLD_NAME': 'reInvent2019_track', 'NUMBER_OF_OBSTACLES': '0',
              'NUMBER_OF_BOT_CARS': '0'}


def test_known_tracks_loaded():
    tracks = known_tracks()
    assert 'reInvent2019_track' in tracks
    assert len(tracks) == 127


def test_valid_config_passes():
    validate_configs(DISCRETE_AGENT, GOOD_TRACK)   # no raise


def test_misspelled_world_raises_with_suggestion():
    bad = dict(GOOD_TRACK, WORLD_NAME='reInvent2019_trac')   # typo
    with pytest.raises(ValueError) as e:
        validate_configs(DISCRETE_AGENT, bad)
    assert 'Did you mean' in str(e.value)
    assert 'reInvent2019_track' in str(e.value)


def test_unknown_world_no_suggestion_still_raises():
    bad = dict(GOOD_TRACK, WORLD_NAME='totally_not_a_track_zzz')
    with pytest.raises(ValueError, match='Unknown WORLD_NAME'):
        validate_configs(DISCRETE_AGENT, bad)


def test_two_cameras_rejected():
    agent = dict(DISCRETE_AGENT, sensor=['STEREO_CAMERAS', 'FRONT_FACING_CAMERA'])
    with pytest.raises(ValueError, match='one camera'):
        validate_configs(agent, GOOD_TRACK)


def test_lidar_only_rejected():
    agent = dict(DISCRETE_AGENT, sensor=['LIDAR'])
    with pytest.raises(ValueError, match='only sensor'):
        validate_configs(agent, GOOD_TRACK)


def test_unsupported_sensor_rejected():
    agent = dict(DISCRETE_AGENT, sensor=['SECTOR_LIDAR', 'LIDAR'])
    with pytest.raises(ValueError, match='Unsupported sensor'):
        validate_configs(agent, GOOD_TRACK)


def test_non_integer_obstacle_count_rejected():
    bad = dict(GOOD_TRACK, NUMBER_OF_OBSTACLES='two')
    with pytest.raises(ValueError, match='NUMBER_OF_OBSTACLES'):
        validate_configs(DISCRETE_AGENT, bad)


def test_bad_race_type_rejected():
    bad = dict(GOOD_TRACK, RACE_TYPE='DEMOLITION_DERBY')
    with pytest.raises(ValueError, match='RACE_TYPE'):
        validate_configs(DISCRETE_AGENT, bad)


def test_bad_action_space_rejected():
    agent = dict(DISCRETE_AGENT, action_space=[{'speed': 0.6}])   # missing steering_angle
    with pytest.raises(Exception):
        validate_configs(agent, GOOD_TRACK)


def test_effective_world_eval_uses_world_name():
    assert effective_world(GOOD_TRACK, 'Austin', evaluation=True) == 'Austin'
    assert effective_world(GOOD_TRACK, None, evaluation=False) == 'reInvent2019_track'
    assert effective_world(GOOD_TRACK, 'Monaco', evaluation=False) == 'Monaco'


def test_eval_world_validated():
    with pytest.raises(ValueError, match='Unknown WORLD_NAME'):
        validate_configs(DISCRETE_AGENT, GOOD_TRACK, world_name='nope_zzz', evaluation=True)


def test_spec_to_env_has_expected_keys_and_roundtrips():
    spec = SimSpec(identity=make_identity('alice', 0), agent_config=DISCRETE_AGENT,
                   track_config=GOOD_TRACK)
    env = spec_to_env(spec)
    assert env['GYM_PORT'] == str(spec.identity.port)
    assert env['ROS_DOMAIN_ID'] == str(spec.identity.ros_domain_id)
    assert env['DISPLAY'] == spec.identity.display
    assert json.loads(env['DEEPRACER_AGENT_PARAMS']) == DISCRETE_AGENT
    assert json.loads(env['DEEPRACER_ENVIRONMENT_PARAMS']) == GOOD_TRACK
    assert 'EVALUATION' not in env       # only set in eval mode


def test_spec_to_env_eval_mode_sets_eval_vars():
    spec = SimSpec(identity=make_identity('alice', 0), agent_config=DISCRETE_AGENT,
                   track_config=GOOD_TRACK, evaluation=True, world_name='Austin')
    env = spec_to_env(spec)
    assert env['EVALUATION'] == 'true'
    assert env['EVAL_WORLD_NAME'] == 'Austin'
