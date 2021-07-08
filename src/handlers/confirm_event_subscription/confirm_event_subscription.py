import os

from aws_lambda_powertools import Logger
from lambda_decorators import load_json_body, dump_json_body


SERVICE_NAME = os.getenv("SERVICE_NAME")
logger = Logger(service=SERVICE_NAME)


@logger.inject_lambda_context(log_event=True)
@load_json_body
@dump_json_body
def confirm_event_subscription(event, _):
    return {"statusCode": 200, "body": event.get("body", {}).get("challenge")}
