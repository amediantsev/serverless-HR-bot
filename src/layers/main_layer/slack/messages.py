import os
from aws_lambda_powertools import Logger

import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from aws.dynamodb import VacationsTable
from exceptions import ArgumentsError


VACATIONS_DB_TABLE = VacationsTable()

SERVICE_NAME = os.getenv("SERVICE_NAME")
logger = Logger(service=SERVICE_NAME)

slack_client = WebClient()


def generate_block_with_text(text):
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def send_message(workspace_id, text=None, blocks=None, channel=None, webhook_url=None):
    if not (text or blocks):
        raise ArgumentsError("text or blocks must be passed.")
    elif channel and webhook_url:
        raise ArgumentsError("text and blocks cannot be passed together.")
    if not (channel or webhook_url):
        raise ArgumentsError("channel or webhook_url must be passed.")
    elif channel and webhook_url:
        raise ArgumentsError("channel and webhook_url cannot be passed together.")

    if text:
        blocks = [generate_block_with_text(text)]

    try:
        if channel:
            logger.info(f"Sending message to the channel {channel}")
            slack_client.token = VACATIONS_DB_TABLE.get_workspace(workspace_id)["access_token"]
            slack_response = slack_client.chat_postMessage(channel=channel, blocks=blocks)
        else:
            slack_response = requests.post(webhook_url, json={"blocks": blocks})
    except SlackApiError:
        logger.exception("Failed to send message.")
        raise

    return slack_response

