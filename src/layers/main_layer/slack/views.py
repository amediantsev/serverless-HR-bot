import datetime
import os

from aws_lambda_powertools import Logger
from slack_sdk import WebClient
from slack_sdk.models.views import View
from slack_sdk.errors import SlackApiError

from aws.dynamodb import get_notifications_channel_from_db, get_decision_maker_from_db
from slack.messages import generate_block_with_text


SERVICE_NAME = os.getenv("SERVICE_NAME")
logger = Logger(service=SERVICE_NAME)

slack_client = WebClient(token=os.environ["BOT_TOKEN"])


def open_modal_view(trigger_id, modal_view_body):
    try:
        response = slack_client.views_open(trigger_id=trigger_id, view=modal_view_body)
    except SlackApiError:
        logger.exception("Failed to open view.")
        raise
    else:
        logger.info(response.data)


def get_book_vacation_modal_view():
    today_string = str(datetime.date.today())
    return View(
        type="modal",
        callback_id="book_vacation",
        title={"type": "plain_text", "text": "Book a vacation", "emoji": True},
        submit={"type": "plain_text", "text": "Submit", "emoji": True},
        close={"type": "plain_text", "text": "Cancel", "emoji": True},
        blocks=[
            generate_block_with_text("*Please select the vacation start date:*"),
            {
                "type": "actions",
                "block_id": "vacation_dates",
                "elements": [
                    {"type": "datepicker", "initial_date": today_string, "action_id": "vacation_start_date"},
                    {"type": "datepicker", "initial_date": today_string, "action_id": "vacation_end_date"},
                ],
            }
        ]
    )


def get_see_user_vacations_modal_view():
    return View(
        type="modal",
        callback_id="see_user_vacations",
        title={"type": "plain_text", "text": "See vacations", "emoji": True},
        submit={"type": "plain_text", "text": "Submit", "emoji": True},
        close={"type": "plain_text", "text": "Cancel", "emoji": True},
        blocks=[
            {
                "type": "section",
                "block_id": "user_selector",
                "text": {"type": "mrkdwn", "text": "Pick a user to see his (her) vacations:"},
                "accessory": {
                    "type": "users_select",
                    "action_id": "user_selector",
                    "placeholder": {"type": "plain_text", "text": "Select a user"},
                },
            }
        ]
    )


def get_configure_workspace_modal_view():
    decision_maker_selector_block = {
        "type": "section",
        "block_id": "vacations_decision_maker_selector",
        "text": {
            "type": "mrkdwn",
            "text": "Pick a user which will make decisions for vacations:"
        },
        "accessory": {
            "action_id": "vacations_decision_maker_selector",
            "type": "users_select",
            "placeholder": {
                "type": "plain_text",
                "text": "Select a user"
            }
        }
    }
    if decision_maker := get_decision_maker_from_db():
        decision_maker_selector_block["accessory"]["initial_user"] = decision_maker["user_id"]

    notifications_channel_selector_block = {
        "type": "section",
        "block_id": "approved_vacations_notifications_selector",
        "text": {
            "type": "mrkdwn",
            "text": "Pick a channel for notifications about approved vacations:"
        },
        "accessory": {
            "action_id": "approved_vacations_notifications_selector",
            "type": "channels_select",
            "placeholder": {
                "type": "plain_text",
                "text": "Select a channel"
            }
        }
    }
    if notifications_channel := get_notifications_channel_from_db():
        notifications_channel_selector_block["accessory"]["initial_channel"] = notifications_channel["channel_id"]

    return View(
        type="modal",
        callback_id="configure_workspace",
        title={"type": "plain_text", "text": "Configure workspace", "emoji": True},
        submit={"type": "plain_text", "text": "Submit", "emoji": True},
        close={"type": "plain_text", "text": "Cancel", "emoji": True},
        blocks=[
            decision_maker_selector_block,
            notifications_channel_selector_block
        ]
    )
