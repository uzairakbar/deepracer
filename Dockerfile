# set base image
#
# All behavior that previous versions patched on top of uzairakbar/deepracer:v0
# (camera path fix, environment-response info enrichment, kinesis off, LIDAR
# range, the gym ZMQ agent, and the sim-only launch) is now baked into
# uzairakbar/deepracer-test:v0, which is built reproducibly from source in the
# deepracer-simapp repository (docker/Dockerfile.zmqsim). See that repo for the
# full provenance of these changes.
FROM uzairakbar/deepracer-test:v0

# set working directory
WORKDIR /opt/ml/code/

ENTRYPOINT ["/opt/ml/code/entrypoint.sh"]
