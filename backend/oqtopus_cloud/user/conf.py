from aws_lambda_powertools import Logger, Metrics, Tracer

logger: Logger = Logger()
tracer: Tracer = Tracer()
metrics: Metrics = Metrics()

logger.setLevel("INFO")
