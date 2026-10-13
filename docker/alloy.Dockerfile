# Grafana Alloy with the rs-recruiting observability pipeline baked in.
#
# The public grafana/alloy image ships no config, and Fargate has no easy way to
# mount one, so the config is built into the image. CI pushes this to the Ops
# ECR repo rs-recruiting/alloy; the tofu ecs-service module runs it as the OTLP
# sidecar in every ECS task (api + worker).
#
# Build from the repo root:
#   docker build -f docker/alloy.Dockerfile -t rs-recruiting-alloy:local .
#
# Runtime config (env vars) is injected by the task definition — see the header
# of alloy/config.alloy. The default grafana/alloy entrypoint runs
# `/etc/alloy/config.alloy`.

FROM grafana/alloy:v1.20.1

# config.alloy = OTLP pipeline (loaded by every sidecar).
# cloudwatch.alloy = the AWS CloudWatch scrape, loaded only when Alloy runs
# against the whole /etc/alloy directory — the ecs-service module does that on
# the single web task; worker sidecars point at config.alloy alone.
COPY alloy/config.alloy /etc/alloy/config.alloy
COPY alloy/cloudwatch.alloy /etc/alloy/cloudwatch.alloy
