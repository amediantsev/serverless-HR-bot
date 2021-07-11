import os
from aws_lambda_powertools import Logger

from slack_sdk import WebClient


SERVICE_NAME = os.getenv("SERVICE_NAME")
logger = Logger(service=SERVICE_NAME)

slack_client = WebClient(token=os.environ["BOT_TOKEN"])


def get_channel_members(channel_id):
    return slack_client.conversations_members(channel=channel_id).data["members"]
