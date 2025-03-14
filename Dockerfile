# set base image
FROM uzairakbar/deepracer:v0

# make required directories
RUN mkdir -p /patches
RUN mkdir -p /configs
RUN mkdir -p /logs/deepracer

# copy over required files
COPY ./configs/* /configs
COPY ./patches/* /patches

# install yq
RUN wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/bin/yq &&\
    chmod +x /usr/bin/yq

# fix broken path for sensors
RUN file1_path='/opt/amazon/markov/camera_utils.py' && \
    file2_path='/opt/amazon/install/sagemaker_rl_agent/lib/python3.6/site-packages/markov/camera_utils.py' && \
    pattern='model_name="/{}/{}"' && \
    replace='model_name="{}/{}"' && \
    sed -i -e "s|$pattern|$replace|g" "$file1_path" "$file2_path"
RUN file1_path='/opt/amazon/markov/camera_utils.py' && \
    file2_path='/opt/amazon/install/sagemaker_rl_agent/lib/python3.6/site-packages/markov/camera_utils.py' && \
    pattern='model_name="/{}".format("sub_camera")' && \
    replace='model_name="{}".format("sub_camera")' && \
    sed -i -e "s|$pattern|$replace|g" "$file1_path" "$file2_path"

# patch environment response (`info` dictionary for `env.step()`)
RUN file_path='/opt/amazon/install/sagemaker_rl_agent/lib/python3.6/site-packages/markov/multi_agent_coach/multi_agent_level_manager.py' && \
    patch='/patches/environment_response.py' && \
    cat "$patch" "$file_path" > temp && mv temp "$file_path"
RUN file_path='/opt/amazon/install/sagemaker_rl_agent/lib/python3.6/site-packages/markov/multi_agent_coach/multi_agent_level_manager.py' && \
    pattern="agent.observe(env_response)" && \
    replace="agent.observe(response(agent, self.environment, env_response))" && \
    sed -i -e "s|$pattern|$replace|g" "$file_path"

# use customized launch script
RUN mv -f /patches/launch-simapp-rosnodes.sh /opt/ml/code/
RUN chmod +x /opt/ml/code/launch-simapp-rosnodes.sh

# set working directory
WORKDIR /opt/ml/code/

ENTRYPOINT ["entrypoint.sh"]