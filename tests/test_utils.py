"""Tests for src.utils: the dict-config API (demo/evaluate), relaxed labeling,
the project-track evaluation loop, artifact locations, and end-to-end smokes on
the real fake-sim.
"""
from types import SimpleNamespace

import pytest
from gymnasium import spaces

import src.utils as u
from src.agents import RandomAgent

from tests.conftest import requires_docker


# a discrete agent-config the fake-sim can serve (stereo + lidar, 3 actions)
AGENT = {
    'action_space': [{'steering_angle': 30, 'speed': 0.6},
                     {'steering_angle': 0, 'speed': 0.6},
                     {'steering_angle': -30, 'speed': 0.6}],
    'sensor': ['STEREO_CAMERAS', 'LIDAR'],
    'action_space_type': 'discrete', 'version': '6',
}


def _discrete_random_agent(n=3):
    # RandomAgent only needs an object exposing .action_space
    return RandomAgent(environment=SimpleNamespace(action_space=spaces.Discrete(n)))


class _StubAgent:
    name = 'ag'
    def eval(self): return self
    def to(self, device): return self
    def get_action(self, x): return 0


# --- pure units (no sim) -----------------------------------------------------
def test_get_race_type_relaxed_labels():
    g = u.get_race_type
    assert g({'NUMBER_OF_OBSTACLES': '0', 'NUMBER_OF_BOT_CARS': '0'}) == 'time_trial'
    assert g({'NUMBER_OF_OBSTACLES': '6', 'NUMBER_OF_BOT_CARS': '0'}) == 'obstacle_avoidance'
    assert g({'NUMBER_OF_OBSTACLES': '3', 'NUMBER_OF_BOT_CARS': '0'}) == 'obstacle_avoidance'
    assert g({'NUMBER_OF_OBSTACLES': '0', 'NUMBER_OF_BOT_CARS': '3'}) == 'head_to_bot'
    assert g({'NUMBER_OF_OBSTACLES': '0', 'NUMBER_OF_BOT_CARS': '9'}) == 'head_to_bot'
    assert g({'NUMBER_OF_OBSTACLES': '2', 'NUMBER_OF_BOT_CARS': '2'}) == 'obstacle_and_bot'
    assert g({}) == 'time_trial'                      # sparse -> never raises


def test_race_config():
    assert u.race_config('obstacle_avoidance', 'Austin') == {
        'NUMBER_OF_OBSTACLES': '6', 'NUMBER_OF_BOT_CARS': '0', 'WORLD_NAME': 'Austin',
    }
    with pytest.raises(ValueError):
        u.race_config('nope', 'Austin')


def test_get_world_name():
    assert u.get_world_name({'WORLD_NAME': 'Vegas_track'}) == 'Vegas_track'
    assert u.get_world_name() == 'reInvent2019_track'      # packaged default


def test_default_dirs_under_artifacts():
    for d in (u.DEMOS_DIR, u.EVAL_DIR, u.PLOTS_DIR, u.RUNS_DIR, u.MODELS_DIR):
        assert d.startswith('./artifacts/')


def test_evaluate_loops_project_tracks_ignoring_world(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(
        u, '_eval_one',
        lambda agent, ac, tc: (seen.append(tc), {'progress': [100.0], 'lap_time': [1.0]})[1],
    )
    result = u.evaluate(
        _StubAgent(),
        track_config={'WORLD_NAME': 'Austin',           # must be IGNORED
                      'NUMBER_OF_OBSTACLES': '6', 'NUMBER_OF_BOT_CARS': '0'},
        directory=str(tmp_path),
    )
    # ran once per project track, in order; the input WORLD_NAME was ignored
    assert [tc['WORLD_NAME'] for tc in seen] == u.PROJECT_TRACKS
    # ...but the obstacle/bot counts were reused across all three
    assert all(tc['NUMBER_OF_OBSTACLES'] == '6' for tc in seen)
    assert set(result) == set(u.PROJECT_TRACKS)
    # aggregate json written, labeled by the (relaxed) race type
    assert (tmp_path / 'obstacle_avoidance-ag.json').exists()


def test_plot_metrics_writes_pdf(tmp_path):
    data = {
        'reInvent2019_track': {'progress': [100.0, 50.0], 'lap_time': [1.5, float('nan')]},
        'Vegas_track': {'progress': [100.0], 'lap_time': [2.0]},
    }
    u.plot_metrics(data, title='smoke', directory=str(tmp_path))
    assert (tmp_path / 'smoke.pdf').exists()


# --- end-to-end smokes on the real fake-sim ----------------------------------
@requires_docker
def test_demo_smoke_non_canonical_combo(sim_env, tmp_path, monkeypatch):
    # a deliberately non-canonical combo (3 obstacles) to prove flexibility
    monkeypatch.setattr(u, 'MAX_DEMO_STEPS', 10)
    agent = _discrete_random_agent(3)
    track = {'NUMBER_OF_OBSTACLES': '3', 'NUMBER_OF_BOT_CARS': '0',
             'WORLD_NAME': 'reInvent2019_track'}
    u.demo(agent, agent_config=AGENT, track_config=track, directory=str(tmp_path))
    videos = list(tmp_path.glob('*.mp4'))
    assert videos, 'demo produced no video'
    assert any('obstacle_avoidance' in v.name and 'reInvent2019_track' in v.name
               for v in videos)


@requires_docker
def test_evaluate_track_smoke(sim_env, tmp_path, monkeypatch):
    monkeypatch.setattr(u, 'EVAL_EPISODES', 1)
    monkeypatch.setattr(u, 'MAX_EVAL_STEPS', 60)
    agent = _discrete_random_agent(3)
    track = u.race_config('time_trial', 'reInvent2019_track')
    metrics = u.evaluate_track(agent, agent_config=AGENT, track_config=track,
                               directory=str(tmp_path))
    assert set(metrics) == {'progress', 'lap_time'}
    assert len(metrics['progress']) == 1
    import json
    data = json.loads((tmp_path / 'time_trial-random.json').read_text())
    assert 'reInvent2019_track' in data
