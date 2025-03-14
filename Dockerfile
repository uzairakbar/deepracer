# set base image
FROM uzairakbar/deepracer:v0

# make config/log directories
RUN mkdir -p /configs
RUN mkdir -p /logs

# install yq
RUN wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/bin/yq &&\
    chmod +x /usr/bin/yq

# set working directory
WORKDIR /opt/ml/code/

ENTRYPOINT ["entrypoint.sh"]