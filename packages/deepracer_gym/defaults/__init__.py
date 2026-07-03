# Packaged default configs (agent_params.json, environment_params.yaml,
# reward_function.py) and the frozen track list (tracks.txt), so the package
# works from any cwd without the repo's top-level configs/ directory.
import json
import importlib.resources as resources


def _read(name: str) -> str:
    return resources.files('deepracer_gym.defaults').joinpath(name).read_text()


def default_agent_config() -> dict:
    return json.loads(_read('agent_params.json'))


def default_track_config() -> dict:
    import yaml   # pyyaml
    return yaml.safe_load(_read('environment_params.yaml'))


def default_reward_function():
    '''The packaged default reward function (used when the caller passes none).

    Prefer a repo-local ``configs.reward_function`` if importable (back-compat
    with the current project layout); otherwise fall back to the packaged copy.
    Loaded lazily so importing the package never depends on cwd.
    '''
    try:
        from configs.reward_function import reward_function
        return reward_function
    except Exception:
        namespace: dict = {}
        exec(_read('reward_function.py'), namespace)
        return namespace['reward_function']
