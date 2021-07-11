import datetime
from enum import Enum
import json
import os

from aws_lambda_powertools import Logger
from boto3.dynamodb.types import TypeDeserializer

from decorators import uncaught_exceptions_handler
from slack.messages import send_message
from aws.dynamodb import (
    delete_vacation_from_db,
    EntityType,
    get_notifications_channel_from_db,
    get_decision_maker_from_db, update_vacation_status
)
from slack.users import get_user


deserializer = TypeDeserializer()
SERVICE_NAME = os.getenv("SERVICE_NAME")
logger = Logger(service=SERVICE_NAME)

VACATION_DATES_FORMATTING = "%Y-%m-%d"
VACATION_DATES_FORMATTING_TO_DISPLAY = "%d.%m.%Y"


VACATION_STATUSES_RESPONSES_MAPPING = {
    "DECLINED": ":neutral_face:. Contact your manager to get more information.",
    "APPROVED": ":tada:. Have a good rest!"
}


class SeasonEmojiSet(Enum):
    SUMMER = ":palm_tree::airplane::sun_with_face::umbrella_on_ground:"
    AUTUMN = ":maple_leaf::jack_o_lantern::coffee::fallen_leaf:"
    WINTER = ":snowboarder::skin-tone-2::christmas_tree::snowman::snowflake:"
    SPRING = ":bouquet::sun_with_face::strawberry::blossom:"


def generate_emoji_set_by_season(vacation_start_date):
    vacation_month = vacation_start_date.month
    if vacation_month < 3 or vacation_month == 12:
        return SeasonEmojiSet.WINTER.value
    elif vacation_month < 6:
        return SeasonEmojiSet.SPRING.value
    elif vacation_month < 9:
        return SeasonEmojiSet.SUMMER.value
    else:
        return SeasonEmojiSet.AUTUMN.value


def generate_block_id_for_vacation_decision(user_id, vacation_id):
    return json.dumps({"event": "vacation_decision", "user_id": user_id, "vacation_id": vacation_id})


def notify_team_about_approved_vacation(vacation, notifications_channel_id):
    start_date = datetime.datetime.strptime(vacation["vacation_start_date"], VACATION_DATES_FORMATTING)
    end_date = datetime.datetime.strptime(vacation["vacation_end_date"], VACATION_DATES_FORMATTING)
    text = f"@{get_user(vacation['user_id'])['name']} booked *vacation* for the following dates:\n\n" \
           f"*{start_date.strftime(VACATION_DATES_FORMATTING_TO_DISPLAY)} - " \
           f"{end_date.strftime(VACATION_DATES_FORMATTING_TO_DISPLAY)}*\n\n" \
           f"{generate_emoji_set_by_season(start_date)}"
    send_message(text, channel=notifications_channel_id)


def notify_requester_about_new_vacation_status(vacation):
    start_date = datetime.datetime.strptime(vacation["vacation_start_date"], VACATION_DATES_FORMATTING)
    end_date = datetime.datetime.strptime(vacation["vacation_end_date"], VACATION_DATES_FORMATTING)
    new_vacation_status = vacation["vacation_status"]
    text = f"Your requested *vacation* for the following dates:\n\n" \
           f"*{start_date.strftime(VACATION_DATES_FORMATTING_TO_DISPLAY)} - " \
           f"{end_date.strftime(VACATION_DATES_FORMATTING_TO_DISPLAY)}*\n\n" \
           f"was *{new_vacation_status.lower()}* "
    text += VACATION_STATUSES_RESPONSES_MAPPING[new_vacation_status]

    send_message(text, channel=vacation["user_id"])


def send_vacation_for_approvement(vacation, decision_maker_id):
    start_date = datetime.datetime.strptime(vacation["vacation_start_date"], VACATION_DATES_FORMATTING)
    end_date = datetime.datetime.strptime(vacation["vacation_end_date"], VACATION_DATES_FORMATTING)
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"@{get_user(vacation['user_id'])['name']} "
                        f"want to book a *vacation* for the following dates:\n\n"
            }
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{start_date.strftime(VACATION_DATES_FORMATTING_TO_DISPLAY)} - "
                        f"{end_date.strftime(VACATION_DATES_FORMATTING_TO_DISPLAY)}*\n\n"
            }
        },
        {"type": "divider"},
        {
            "type": "actions",
            "block_id": generate_block_id_for_vacation_decision(vacation["user_id"], vacation["vacation_id"]),
            "elements": [
                {
                    "type": "button",
                    "action_id": "approve_vacation",
                    "text": {
                        "type": "plain_text",
                        "text": "Approve",
                        "emoji": True
                    },
                    "value": "APPROVED"
                },
                {
                    "type": "button",
                    "action_id": "decline_vacation",
                    "text": {
                        "type": "plain_text",
                        "text": "Decline",
                        "emoji": True
                    },
                    "value": "DECLINED",
                }
            ]
        }
    ]
    send_message(blocks=blocks, channel=decision_maker_id)


@logger.inject_lambda_context(log_event=True)
@uncaught_exceptions_handler
def process_vacations(event, _):
    for record in event["Records"]:
        record_sk = record["dynamodb"]["Keys"]["sk"]["S"]
        if record_sk.startswith(f"{EntityType.VACATION.value}#"):
            vacation = {
                key: deserializer.deserialize(value)
                for key, value in record["dynamodb"].get("NewImage", {}).items()
            }

            if (event_name := record["eventName"]) == "MODIFY":
                if (
                    (new_vacation_status := vacation["vacation_status"]) == "APPROVED"
                    and (notifications_channel := get_notifications_channel_from_db())
                ):
                    notify_team_about_approved_vacation(vacation, notifications_channel["channel_id"])
                elif new_vacation_status == "DECLINED":
                    delete_vacation_from_db(vacation["user_id"], vacation["vacation_id"])
                notify_requester_about_new_vacation_status(vacation)

            elif event_name == "INSERT":
                user_id = vacation["user_id"]
                if decision_maker := get_decision_maker_from_db():
                    send_message(
                        "Vacation has been sent for approval :stuck_out_tongue_winking_eye::+1:",
                        channel=user_id
                    )
                    send_vacation_for_approvement(vacation, decision_maker["user_id"])
                else:
                    update_vacation_status(user_id, vacation["vacation_id"], "APPROVED")
