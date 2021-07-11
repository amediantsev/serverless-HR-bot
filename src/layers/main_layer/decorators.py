from http import HTTPStatus
import os

from aws_lambda_powertools import Logger
from slack.messages import send_message


logger = Logger(service="HR-slack-bot")


def uncaught_exceptions_handler(lambda_func):
    def catch_error(*args, **kwargs):
        try:
            lambda_response = lambda_func(*args, **kwargs)
        except Exception as e:
            send_message(
                text=f"Lambda: {lambda_func.__name__}\nError: {e}", channel=os.getenv("BOT_HEALTH_CHANNEL_ID")
            )
            logger.exception("Unexpected error")
            return {"statusCode": HTTPStatus.OK}
        else:
            return lambda_response
    return catch_error

