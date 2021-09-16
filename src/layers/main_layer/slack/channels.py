from slack_sdk import WebClient

from aws.dynamodb import VacationsTable


VACATIONS_DB_TABLE = VacationsTable()

slack_client = WebClient()


def get_channel_members(workspace_id, channel_id):
    slack_client.token = VACATIONS_DB_TABLE.get_workspace(workspace_id)["access_token"]
    return slack_client.conversations_members(channel=channel_id).data["members"]
