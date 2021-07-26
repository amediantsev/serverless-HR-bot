import os

from slack_sdk import WebClient


slack_client = WebClient(token=os.environ["BOT_TOKEN"])


def get_channel_members(channel_id):
    return slack_client.conversations_members(channel=channel_id).data["members"]
