import os

from aws_lambda_powertools import Logger, Metrics, Tracer

logger: Logger = Logger()
tracer: Tracer = Tracer()
metrics: Metrics = Metrics()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logger.setLevel(LOG_LEVEL)
