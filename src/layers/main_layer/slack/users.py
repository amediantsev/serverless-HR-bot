import os

from slack_sdk import WebClient

from aws.dynamodb import VacationsTable


VACATIONS_DB_TABLE = VacationsTable()


slack_client = WebClient()


def get_bot_user_id(workspace_id):
    slack_client.token = VACATIONS_DB_TABLE.get_workspace(workspace_id)["access_token"]
    return slack_client.auth_test().data["user_id"]


def get_user(workspace_id, user_id):
    slack_client.token = VACATIONS_DB_TABLE.get_workspace(workspace_id)["access_token"]
    return slack_client.users_info(user=user_id).data["user"]
