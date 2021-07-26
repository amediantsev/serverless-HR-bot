import os
from aws_lambda_powertools import Logger

from slack_sdk import WebClient

from aws.ssm import get_parameter


SERVICE_NAME = os.getenv("SERVICE_NAME")
logger = Logger(service=SERVICE_NAME)

slack_client = WebClient(token=os.environ["BOT_TOKEN"])

CLIENT_ID = get_parameter(os.getenv("CLIENT_ID_SSM_PARAM"), decrypted=True)
CLIENT_SECRET = get_parameter(os.getenv("CLIENT_SECRET_SSM_PARAM"), decrypted=True)


def exchange_oauth_token(exchange_token, redirect_uri):
    return slack_client.oauth_v2_access(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        code=exchange_token,
        redirect_uri=redirect_uri
    )
