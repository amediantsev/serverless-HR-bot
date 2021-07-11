import os
from aws_lambda_powertools import Logger

from slack_sdk import WebClient


SERVICE_NAME = os.getenv("SERVICE_NAME")
logger = Logger(service=SERVICE_NAME)

slack_client = WebClient(token=os.environ["BOT_TOKEN"])


def get_bot_user_id():
    logger.info(slack_client.auth_test().data)
    return slack_client.auth_test().data["user_id"]


def get_user(user_id):
    return slack_client.users_info(user=user_id).data["user"]
