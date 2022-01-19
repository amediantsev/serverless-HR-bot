from http import HTTPStatus
import os

from aws_lambda_powertools import Logger

from aws.ssm import get_parameter
from slack.messages import send_message


SERVICE_NAME = os.getenv("SERVICE_NAME")
logger = Logger(service=SERVICE_NAME)

ROOT_WORKSPACE_ID_SSM_PARAM = os.getenv("ROOT_WORKSPACE_ID_SSM_PARAM")
ROOT_BOT_HEALTH_CHANNEL_ID_SSM_PARAM = os.getenv("ROOT_BOT_HEALTH_CHANNEL_ID_SSM_PARAM")


def uncaught_exceptions_handler(lambda_func):
    def catch_error(*args, **kwargs):
        try:
            lambda_response = lambda_func(*args, **kwargs)
        except Exception as e:
            send_message(
                workspace_id=get_parameter(ROOT_WORKSPACE_ID_SSM_PARAM, decrypted=True),
                text=f"Lambda: {lambda_func.__name__}.\nError: {e}",
                channel=get_parameter(ROOT_BOT_HEALTH_CHANNEL_ID_SSM_PARAM, decrypted=True),
            )
            logger.exception("Unexpected error")
            return {"statusCode": HTTPStatus.OK}
        else:
            return lambda_response
    return catch_error

