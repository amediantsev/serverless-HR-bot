import os

from slack_sdk import WebClient


slack_client = WebClient(token=os.environ["BOT_TOKEN"])


def get_bot_user_id():
    return slack_client.auth_test().data["user_id"]


def get_user(user_id):
    return slack_client.users_info(user=user_id).data["user"]
