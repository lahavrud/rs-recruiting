from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import ECR, ECS, Lambda
from diagrams.aws.database import RDS
from diagrams.aws.integration import SNS, SQS
from diagrams.aws.management import SSM, Cloudwatch
from diagrams.aws.network import CloudFront
from diagrams.aws.storage import S3
from diagrams.generic.network import Firewall
from diagrams.onprem.ci import GithubActions
from diagrams.onprem.client import Users

graph_attr = {
    "fontsize": "14",
    "bgcolor": "white",
    "pad": "2.0",
    "splines": "curved",
    "nodesep": "1.0",
    "ranksep": "2.2",
    "overlap": "false",
}

node_attr = {
    "fontsize": "12",
    "margin": "0.4,0.3",
}

with Diagram(
    "RS Recruiting — AWS Architecture",
    filename="docs/screenshots/aws-architecture",
    outformat="png",
    show=False,
    graph_attr=graph_attr,
    node_attr=node_attr,
    direction="LR",
):
    # ── Left: ingress ──────────────────────────────────────────
    users = Users("Users")
    cloudflare = Firewall("Cloudflare\nDNS only")

    with Cluster("AWS  us-east-1"):
        # CDN layer
        cf = CloudFront("CloudFront\nCDN + TLS\nACM cert")
        le = Lambda("Lambda@Edge\nbot detection")

        # Serving layer
        s3_fe = S3("S3 Frontend\nSPA bundle")
        ecs = ECS("ECS Fargate\nweb · worker")

        # Data layer
        rds = RDS("RDS\nPostgreSQL 16")
        sqs = SQS("SQS\ntask queue")
        s3_app = S3("S3\nuploads")
        ssm = SSM("SSM\nParameter Store")

        # CI / CD
        with Cluster("CI / CD"):
            github = GithubActions("GitHub Actions")
            ecr = ECR("ECR (ops acct)")

        # Observability
        with Cluster("Observability"):
            cw = Cloudwatch("CloudWatch\n9 alarms")
            sns = SNS("SNS\nops-alerts")

    # ── Request path ──────────────────────────────────────────
    users >> cloudflare >> cf
    cf >> le
    cf >> Edge(label="SPA") >> s3_fe
    cf >> Edge(label="/api /auth") >> ecs
    ecs >> rds
    ecs >> sqs
    ecs >> s3_app
    ecs >> Edge(style="dashed", label="secrets") >> ssm

    # ── CI / CD ───────────────────────────────────────────────
    github >> ecr >> Edge(label="pull") >> ecs
    github >> Edge(label="bundle") >> s3_fe
    github >> Edge(label="deploy") >> ecs

    # ── Observability ─────────────────────────────────────────
    ecs >> Edge(style="dashed", color="lightgray") >> cw
    rds >> Edge(style="dashed", color="lightgray") >> cw
    cw >> sns
