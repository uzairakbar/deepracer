import os
import json
import torch
import random
import enlighten
import numpy as np
import pandas as pd
import seaborn as sns
import gymnasium as gym
from loguru import logger
from gymnasium import spaces
import matplotlib.pyplot as plt
from gymnasium.wrappers import (
    RecordVideo,
    FlattenObservation,
    RecordEpisodeStatistics
)
from IPython.display import Video, display, clear_output

from deepracer_gym.defaults import resolve_agent_config, resolve_track_config

from src.agents import Agent


PROGRESS_MANAGER = enlighten.get_manager()
FS_TICK: int = 12
FS_LABEL: int = 18
PLOT_DPI: int=1200
PLOT_FORMAT: str='pdf'
RC_PARAMS: dict = {
    # Set background and border settings
    'axes.facecolor': 'white',
    'axes.edgecolor': 'black',
    'axes.linewidth': 2,
    'xtick.color': 'black',
    'ytick.color': 'black',
}
ENVIRONMENT_NAME: str='deepracer-v0'
MAX_DEMO_STEPS: int = 1_000
MAX_EVAL_STEPS: int = 1_000
EVAL_EPISODES: int = 5
ONLY_CPU: bool = False
SEED: int=42

# Default artifact output locations.
ARTIFACTS_DIR: str='./artifacts'
DEMOS_DIR: str=f'{ARTIFACTS_DIR}/demos'
EVAL_DIR: str=f'{ARTIFACTS_DIR}/evaluations'
PLOTS_DIR: str=f'{ARTIFACTS_DIR}/plots'
RUNS_DIR: str=f'{ARTIFACTS_DIR}/runs'        # tensorboard logs (src.run)
MODELS_DIR: str=f'{ARTIFACTS_DIR}/models'    # saved models (src.run)

# The three project tracks evaluate() reports across (increasing difficulty).
PROJECT_TRACKS: list[str]=[
    'reInvent2019_wide',    # A to Z Speedway
    'reInvent2019_track',   # Smile Speedway
    'Vegas_track',          # AWS Summit Raceway
]
# Canonical race types are an OPTIONAL convenience for building a track_config;
# they are NOT a restriction — any obstacle/bot combo is accepted everywhere.
RACE_TYPES: dict[str, dict[str, str]]={
    'time_trial':         {'NUMBER_OF_OBSTACLES': '0', 'NUMBER_OF_BOT_CARS': '0'},
    'obstacle_avoidance': {'NUMBER_OF_OBSTACLES': '6', 'NUMBER_OF_BOT_CARS': '0'},
    'head_to_bot':        {'NUMBER_OF_OBSTACLES': '0', 'NUMBER_OF_BOT_CARS': '3'},
}


def race_config(race_type: str, world_name: str) -> dict:
    '''Build a track_config for a canonical race type on a track.'''
    if race_type not in RACE_TYPES:
        raise ValueError(
            f'Unknown race_type {race_type!r}; choose {list(RACE_TYPES)} '
            f'or pass a track_config dict directly.'
        )
    return {**RACE_TYPES[race_type], 'WORLD_NAME': world_name}


def set_seed(seed: int=SEED):
    '''
    set seed for reproducability
    '''
    random.seed(seed)

    np.random.seed(seed)

    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)

    # uncomment this for better reproducibility; slows torch
    # torch.backends.cudnn.deterministic = True
    # torch.backends.cudnn.benchmark = False

    os.environ['PYTHONHASHSEED'] = str(seed)

    logger.info(f'Random seed set as {seed}.')


def device():
    if torch.cuda.is_available():
        device = 'cuda'
    elif torch.backends.mps.is_available():
        device = 'mps'
    else:
        device = 'cpu'

    if ONLY_CPU:
        device = 'cpu'

    logger.info(f'Using {device} device.')
    return torch.device(device)


def make_environment(
        environment_name: str=ENVIRONMENT_NAME,
        seed: int=SEED,
        agent_config: dict | None=None,
        track_config: dict | None=None,
        **kwargs
    ):
    environment = gym.make(
        environment_name,
        agent_config=agent_config,
        track_config=track_config,
        **kwargs
    )

    environment = RecordEpisodeStatistics(
        FlattenObservation(environment)
    )

    environment.action_space.seed(seed)
    environment.observation_space.seed(seed)

    return environment


def get_world_name(track_config: dict | None=None):
    '''The track a config points at (WORLD_NAME); None -> packaged default.'''
    return resolve_track_config(track_config)['WORLD_NAME']


def get_race_type(track_config: dict | None=None):
    '''Artifact label for the obstacle/bot counts in track_config.'''
    tc = resolve_track_config(track_config)
    obstacles = int(tc.get('NUMBER_OF_OBSTACLES', 0))
    bots = int(tc.get('NUMBER_OF_BOT_CARS', 0))
    if obstacles == 0 and bots == 0:
        return 'time_trial'
    if bots == 0:
        return 'obstacle_avoidance'      # any number of obstacles
    if obstacles == 0:
        return 'head_to_bot'             # any number of bot cars
    return 'obstacle_and_bot'            # mixed; label only


def _to_env_action(action, action_space):
    '''Coerce an agent's action to what the environment's step expects.'''
    if not isinstance(action, np.ndarray) and torch.is_tensor(action):
        action = action.cpu().detach().numpy()
    if isinstance(action_space, spaces.Discrete):
        action = action.item() if hasattr(action, 'item') else int(action)
    return action


def _check_agent_env_compatible(agent: Agent, environment, observation):
    '''Fail fast (before a whole run) if the agent does not fit the environment
    built from this agent_config, such as a mismatched action space or an encoder
    that chokes on the observation shape.'''
    try:
        action = agent.get_action(torch.Tensor(observation)[None, :])
        action = _to_env_action(action, environment.action_space)
        fits = environment.action_space.contains(action)
    except Exception as e:
        raise ValueError(
            'agent is incompatible with the environment built from this agent_config '
            '-- pass the agent_config you trained with.'
        ) from e
    if not fits:
        raise ValueError(
            'agent action does not fit the environment action space '
            '-- pass the agent_config you trained with.'
        )


def demo(
        agent: Agent,
        agent_config: dict | None=None,
        track_config: dict | None=None,
        directory: str=DEMOS_DIR               # directory to save videos
    ):
    '''Record a video for the environment defined by agent_config and track_config.'''
    agent_config = resolve_agent_config(agent_config)
    track_config = resolve_track_config(track_config)
    world_name = get_world_name(track_config)
    race_type = get_race_type(track_config)

    demo_device = torch.device('cpu')
    agent.eval().to(demo_device)
    os.makedirs(directory, exist_ok=True)

    # create environment with proper render_mode
    demo_environment = make_environment(
        render_mode='rgb_array',
        agent_config=agent_config, track_config=track_config,
    )

    # apply video recording wrapper
    demo_environment = RecordVideo(
        demo_environment,
        video_folder=directory,
        episode_trigger=lambda x: True,
        name_prefix=f'{world_name}-{race_type}-{agent.name}'
    )

    observation, info = demo_environment.reset()
    _check_agent_env_compatible(agent, demo_environment, observation)
    prev_sim_time = info['reward_params']['sim_time']
    total_sim_dt = 0.0
    n_sim_dt = 0

    demo_progress = PROGRESS_MANAGER.counter(
        total=MAX_DEMO_STEPS, desc=f'{world_name} {race_type} demo', unit='steps', leave=False
    )
    for t in range(MAX_DEMO_STEPS):
        # get action from policy
        action = agent.get_action(torch.Tensor(observation)[None, :])
        action = _to_env_action(action, demo_environment.action_space)

        # execute the action, get observation
        observation, _, terminated, truncated, info = demo_environment.step(
            action
        )

        # update the running sim-time-per-step estimate and set the video fps
        sim_time = info['reward_params']['sim_time']
        sim_dt = sim_time - prev_sim_time
        prev_sim_time = sim_time
        if sim_dt > 0:
            total_sim_dt += sim_dt
            n_sim_dt += 1
            demo_environment.frames_per_sec = max(1, round(n_sim_dt / total_sim_dt))

        demo_progress.update()
        demo_progress.refresh()

        if terminated or truncated:
            break

    demo_environment.close()
    demo_progress.close()

    # The RecordVideo wrapper names the file automatically with the prefix + step info
    # We'll grab the latest video with our given prefix
    # e.g. 'agent_rl-video-episode-0.mp4' or similar
    filtered_videos = sorted(
        f for f in os.listdir(directory)
        if (
            f.endswith('.mp4')
            and
            agent.name in f
            and
            world_name in f
            and
            race_type in f
        )
    )
    if len(filtered_videos) == 0:
        logger.warning('No videos found!')
        return

    # display the latest video
    video_path = os.path.join(
        directory, filtered_videos[-1]
    )

    clear_output(wait=True)
    display(
        Video(video_path, embed=True)
    )


def _run_eval_episodes(agent: Agent, environment, world_name: str):
    '''Run EVAL_EPISODES on an already-built eval environment.'''
    observation, info = environment.reset()
    _check_agent_env_compatible(agent, environment, observation)

    eval_metrics = {
        'progress': [],
        'lap_time': [],
    }
    evaluation_progress = PROGRESS_MANAGER.counter(
        total=EVAL_EPISODES, desc=f'Evaluating {world_name}', unit='episodes'
    )
    for episode in range(EVAL_EPISODES):

        # absolute sim clock at the episode start
        start_sim_time = info['reward_params']['sim_time']

        episode_progress = PROGRESS_MANAGER.counter(
            total=MAX_EVAL_STEPS, desc=f'Episode {episode}', unit='steps', leave=False
        )
        for t in range(MAX_EVAL_STEPS):

            action = agent.get_action(torch.Tensor(observation)[None, :])
            action = _to_env_action(action, environment.action_space)

            observation, reward, terminated, truncated, info = environment.step(
                action
            )

            episode_progress.update()
            episode_progress.refresh()

            done = terminated or truncated
            if done or t == MAX_EVAL_STEPS - 1:
                progress = info['reward_params']['progress']
                lap = lap_time(info, start_sim_time)

                eval_metrics['progress'].append(
                    progress
                )
                eval_metrics['lap_time'].append(
                    lap
                )

                logger.info(
                    f'Episode {episode}:\t progress: {progress}\t lap_time: {lap}'
                )

                observation, info = environment.reset()

                break

        episode_progress.close()

        evaluation_progress.update()
        evaluation_progress.refresh()
    evaluation_progress.close()

    return eval_metrics


def _eval_one(agent: Agent, agent_config: dict, track_config: dict):
    '''Evaluate one track_config and tear down its simulator.'''
    world_name = get_world_name(track_config)
    eval_environment = make_environment(
        evaluation=True, world_name=world_name,
        agent_config=agent_config, track_config=track_config,
    )
    try:
        return _run_eval_episodes(agent, eval_environment, world_name)
    finally:
        eval_environment.close()


def _write_eval_metrics(directory, race_type, agent_name, metrics, overwrite=False):
    '''Write {world_name: metrics} to <dir>/<race_type>-<agent>.json. Merges with
    any existing file unless overwrite=True.'''
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f'{race_type}-{agent_name}.json')
    data = {}
    if not overwrite and os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}
    data.update(metrics)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def evaluate_track(
        agent: Agent,
        agent_config: dict | None=None,
        track_config: dict | None=None,
        directory: str=EVAL_DIR
    ):
    '''Evaluate an agent on a single track (WORLD_NAME + counts from track_config)
    over EVAL_EPISODES episodes; returns and saves progress + lap-time.'''
    agent_config = resolve_agent_config(agent_config)
    track_config = resolve_track_config(track_config)
    world_name = get_world_name(track_config)
    race_type = get_race_type(track_config)

    logger.info(
        f'Starting {race_type} evaluation on {world_name} track.'
    )

    agent.eval().to(torch.device('cpu'))
    eval_metrics = _eval_one(agent, agent_config, track_config)
    _write_eval_metrics(directory, race_type, agent.name, {world_name: eval_metrics})
    return eval_metrics


def evaluate(
        agent: Agent,
        agent_config: dict | None=None,
        track_config: dict | None=None,
        directory: str=EVAL_DIR
    ):
    '''Evaluate an agent across all three PROJECT_TRACKS (the reported set) using
    the obstacle/bot counts from track_config. WORLD_NAME in track_config is
    ignored (we run all three tracks); None -> packaged default counts.'''
    agent_config = resolve_agent_config(agent_config)
    track_config = resolve_track_config(track_config)
    race_type = get_race_type(track_config)
    if 'WORLD_NAME' in track_config:
        logger.info(
            'evaluate() runs all PROJECT_TRACKS; ignoring track_config '
            f'WORLD_NAME ({track_config["WORLD_NAME"]!r}).'
        )

    agent.eval().to(torch.device('cpu'))

    status = PROGRESS_MANAGER.status_bar(
        status_format=race_type + u' {fill}Evaluating {track}{fill}{elapsed}',
        color='bold_underline_bright_white_on_lightslategray',
        justify=enlighten.Justify.CENTER, track='<track>',
        autorefresh=True, min_delta=0.5
    )
    eval_metrics = {}
    for world_name in PROJECT_TRACKS:
        status.update(track=world_name)
        status.refresh()
        eval_metrics[world_name] = _eval_one(
            agent, agent_config, {**track_config, 'WORLD_NAME': world_name}
        )
    status.close()

    _write_eval_metrics(directory, race_type, agent.name, eval_metrics, overwrite=True)
    return eval_metrics


def plot_metrics(
        data,
        title,
        directory: str=PLOTS_DIR
    ):

    df_progress = pd.DataFrame([
        {"Track": track, "Progress": progress}
        for track, values in data.items()
        for progress in values["progress"]
    ])

    # Replace NaNs with a large sentinel in lap time data
    df_lap_time = pd.DataFrame([
        {
            "Track": track,
            "Lap Time": lap_time if not np.isnan(lap_time) else 100_000 # default large value
        }
        for track, values in data.items()
        for lap_time in values["lap_time"]
    ])

    os.makedirs(directory, exist_ok=True)
    plt.rcParams.update(RC_PARAMS);
    sns.set_palette('deep')

    # Create the plots
    fig, ax = plt.subplots(1, 2, figsize=(8, 4))

    # hue=Track keeps newer seaborn versions happy when a palette is set.
    sns.boxplot(
        x="Track",
        y="Progress",
        hue="Track",
        legend=False,
        data=df_progress,
        ax=ax[0],
        palette='deep',
        showmeans=True,
        meanprops={
            'markerfacecolor': 'white',
            'markeredgecolor': 'black'
            },
        flierprops={'marker': 'x'}
    );

    # Boxplot for lap time
    sns.boxplot(
        x="Track",
        y="Lap Time",
        hue="Track",
        legend=False,
        data=df_lap_time,
        ax=ax[1],
        palette='deep',
        showmeans=True,
        meanprops={
            'markerfacecolor': 'white',
            'markeredgecolor': 'black'
            },
        flierprops={'marker': 'x'}
    );

    fig.suptitle(title)

    plt.setp(ax[0].get_xticklabels(), rotation=45)
    plt.setp(ax[1].get_xticklabels(), rotation=45)
    ax[1].set_yscale('log')
    plt.grid(axis='y', linestyle='--', alpha=0.7)

    clear_output(wait=True)

    plt.tight_layout()
    plt.show()
    fig.savefig(
        f"{directory}/{title}.{PLOT_FORMAT}", dpi=PLOT_DPI, format=PLOT_FORMAT
    )


def lap_time(info, start_sim_time):
    # Lap time in simulation seconds
    if info['reward_params']['progress'] >= 100:
        return info['reward_params']['sim_time'] - start_sim_time
    else:
        # using in place of float('-inf') for better tensorboard visualizaiton
        return np.nan
