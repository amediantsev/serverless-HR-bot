import os
from aws_lambda_powertools import Logger

import requests as requests


BOT_TOKEN = os.environ["BOT_TOKEN"]
SEND_MESSAGE_URL = "https://slack.com/api/chat.postMessage"
SERVICE_NAME = os.getenv("SERVICE_NAME")
logger = Logger(service=SERVICE_NAME)


def send_markdown_message(text, channel=None, webhook_url=None):
    body = {"blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]}
    if channel:
        body["channel"] = channel
        slack_response = requests.post(SEND_MESSAGE_URL, headers={"Authorization": f"Bearer {BOT_TOKEN}"}, json=body)
    else:
        slack_response = requests.post(webhook_url, json=body)
    slack_response.raise_for_status()
    logger.info(slack_response.json())
    return slack_response

