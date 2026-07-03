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

from deepracer_gym.defaults import resolve_track_config

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
    # agent_config / track_config are dicts (or None -> packaged defaults),
    # passed straight through to the environment.
    environment = gym.make(
        environment_name,
        agent_config=agent_config,
        track_config=track_config,
        **kwargs
    )

    environment = RecordEpisodeStatistics(
        FlattenObservation(environment)
    )

    # environment.seed(seed)
    environment.action_space.seed(seed)
    environment.observation_space.seed(seed)

    return environment


def get_world_name(track_config: dict | None=None):
    track_config = resolve_track_config(track_config)

    if 'WORLD_NAME' not in track_config:
        raise ValueError('WORLD_NAME not defined in track_config.')

    return track_config['WORLD_NAME']


def get_race_type(track_config: dict | None=None):
    track_config = resolve_track_config(track_config)

    obstacles = int(track_config['NUMBER_OF_OBSTACLES'])
    bots = int(track_config['NUMBER_OF_BOT_CARS'])
    if (
        obstacles == 0 and bots == 0
    ):
        return 'time_trial'
    elif (
        obstacles == 6 and bots == 0
    ):
        return 'obstacle_avoidance'
    elif (
        obstacles == 0 and bots == 3
    ):
        return 'head_to_bot'
    else:
        raise ValueError(
            f'Incorrect configuration for NUMBER_OF_OBSTACLES or NUMBER_OF_BOT_CARS.'
        )


def demo(
        agent: Agent,
        agent_config: dict | None=None,
        track_config: dict | None=None,
        environment_name: str=ENVIRONMENT_NAME,
        directory: str='./demos'               # directory to save videos
    ):
    race_type = get_race_type(track_config)
    world_name = get_world_name(track_config)

    demo_device = torch.device('cpu')
    agent.eval().to(demo_device)
    os.makedirs(directory, exist_ok=True)

    # create environment with proper render_mode
    demo_environment = make_environment(
        environment_name, render_mode='rgb_array',
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
    prev_sim_time = info['reward_params']['sim_time']
    total_sim_dt = 0.0
    n_sim_dt = 0

    demo_progress = PROGRESS_MANAGER.counter(
        total=MAX_DEMO_STEPS, desc=f'{world_name} {race_type} demo', unit='steps', leave=False
    )
    for t in range(MAX_DEMO_STEPS):
        # get action from policy
        action = agent.get_action(torch.Tensor(observation)[None, :])

        if not isinstance(action, np.ndarray) and torch.is_tensor(action):
            action = action.cpu().detach().numpy()

        if isinstance(demo_environment.action_space, spaces.Discrete):
            action = action.item()

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


def evaluate_track(
        agent: Agent,
        world_name: str,
        agent_config: dict | None=None,
        track_config: dict | None=None,
        environment_name: str=ENVIRONMENT_NAME,
        directory: str='./evaluations'               # directory to save eval data
    ):
    race_type = get_race_type(track_config)

    logger.info(
        f'Starting {race_type} evaluation on {world_name} track.'
    )

    eval_device = torch.device('cpu')
    agent.eval().to(eval_device)
    os.makedirs(directory, exist_ok=True)

    # The environment now provisions its own sim in evaluation mode on the
    # requested track (no bash restart); closing it below tears the sim down.
    eval_environment = make_environment(
        environment_name, evaluation=True, world_name=world_name,
        agent_config=agent_config, track_config=track_config,
    )
    observation, info = eval_environment.reset()

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

            if not isinstance(action, np.ndarray) and torch.is_tensor(action):
                action = action.cpu().detach().numpy()

            if isinstance(eval_environment.action_space, spaces.Discrete):
                action = action.item()

            observation, reward, terminated, truncated, info = eval_environment.step(
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

                observation, info = eval_environment.reset()
                
                break

        episode_progress.close()
        
        evaluation_progress.update()
        evaluation_progress.refresh()
    evaluation_progress.close()
    eval_environment.close()
    
    try:
        with open(f'{directory}/{race_type}-{agent.name}.json', '+r') as f:
            all_metrics = json.load(f)
    except:
        all_metrics = {}
    
    all_metrics.update({
        world_name: eval_metrics
    })
    with open(f'{directory}/{race_type}-{agent.name}.json', '+w') as f:
        json.dump(all_metrics, f)
    
    return eval_metrics


def evaluate(
        agent: Agent,
        agent_config: dict | None=None,
        track_config: dict | None=None,
        environment_name: str=ENVIRONMENT_NAME,
        directory: str='./evaluations'               # directory to save eval data
    ):
    race_type = get_race_type(track_config)

    eval_world_names = ([
        'reInvent2019_wide',    # A to Z Speedway
        'reInvent2019_track',   # Smile Speedway
        'Vegas_track',          # AWS Summit Raceway
    ])
    
    eval_device = torch.device('cpu')
    agent.eval().to(eval_device)
    os.makedirs(directory, exist_ok=True)

    status = PROGRESS_MANAGER.status_bar(
        status_format=race_type + u' {fill}Evaluating {track}{fill}{elapsed}',
        color='bold_underline_bright_white_on_lightslategray',
        justify=enlighten.Justify.CENTER, track='<track>',
        autorefresh=True, min_delta=0.5
    )
    eval_metrics = {}
    for world_name in eval_world_names:
        status.update(track=world_name)
        status.refresh()
        eval_metrics[world_name] = evaluate_track(
            agent=agent,
            world_name=world_name,
            agent_config=agent_config,
            track_config=track_config,
            environment_name=environment_name,
            directory=directory
        )
    status.close()
    
    with open(f'{directory}/{race_type}-{agent.name}.json', '+w') as f:
        json.dump(eval_metrics, f)

    return eval_metrics


def plot_metrics(
        data,
        title,
        directory: str='./plots'               # directory to save plots
    ):

    df_progress = pd.DataFrame([
        {"Track": track, "Progress": progress}
        for track, values in data.items()
        for progress in values["progress"]
    ])

    # Replace NaNs with -inf in lap time data
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

    # Boxplot for progress
    sns.boxplot(
        x="Track",
        y="Progress",
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

    # Boxplot for lap time (handling -inf values)
    sns.boxplot(
        x="Track",
        y="Lap Time",
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

    # plt.xlabel(xlabel, fontsize=FS_LABEL)
    # plt.ylabel(ylabel, fontsize=FS_LABEL)
    # plt.yticks(fontsize=FS_TICK)
    # plt.xticks(fontsize=FS_TICK)
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