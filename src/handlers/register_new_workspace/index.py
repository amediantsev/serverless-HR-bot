import os
from http import HTTPStatus

from aws_lambda_powertools import Logger

from aws.dynamodb import VacationsTable
from decorators import uncaught_exceptions_handler
from slack.auth import exchange_oauth_token


SERVICE_NAME = os.getenv("SERVICE_NAME")
logger = Logger(service=SERVICE_NAME)

VACATIONS_DB_TABLE = VacationsTable()


@logger.inject_lambda_context(log_event=True)
@uncaught_exceptions_handler
def register_new_workspace(event, _):
    # TODO Check if request from Slack
    request_context = event["requestContext"]
    oauth_response = exchange_oauth_token(
        exchange_token=event["queryStringParameters"]["code"],
        redirect_uri=f"https://{request_context['domainName']}{request_context['path']}"
    ).data

    if not oauth_response.get("ok"):
        return {
            "statusCode": HTTPStatus.INTERNAL_SERVER_ERROR,
            "headers": {"Content-type": "text/html"},
            "body": "<html><body><h1>Sorry, something went wrong. Try again later, please.</h1></body></html>"
        }

    VACATIONS_DB_TABLE.save_workspace(oauth_response["team"]["id"], oauth_response["access_token"])

    return {
        "statusCode": HTTPStatus.CREATED,
        "headers": {"Content-type": "text/html"},
        "body": "<html><body><h1>HR Bot is installed successfully!</h1></body></html>"
    }
