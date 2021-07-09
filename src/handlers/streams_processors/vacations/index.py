import datetime
from enum import Enum
import json
import os

import requests
from aws_lambda_powertools import Logger

from decorators import uncaught_exceptions_handler
from slack.messages import send_markdown_message, SEND_MESSAGE_URL, BOT_TOKEN
from aws.dynamodb import decode_key, delete_vacation_from_db


logger = Logger(service="HR-slack-bot")

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
        return SeasonEmojiSet.AUTUMN


def generate_block_id_for_vacation_decision(pk, sk):
    return json.dumps({"event": "vacation_decision", "user_id": decode_key(pk), "vacation_id": decode_key(sk)})


def notify_general_about_approved_vacation(vacation):
    start_date = datetime.datetime.strptime(vacation["vacation_start_date"]["S"], VACATION_DATES_FORMATTING)
    end_date = datetime.datetime.strptime(vacation["vacation_end_date"]["S"], VACATION_DATES_FORMATTING)
    text = f"@{vacation['username']['S']} booked *vacation* for the following dates:\n\n" \
           f"*{start_date.strftime(VACATION_DATES_FORMATTING_TO_DISPLAY)} - " \
           f"{end_date.strftime(VACATION_DATES_FORMATTING_TO_DISPLAY)}*\n\n" \
           f"{generate_emoji_set_by_season(start_date)}"
    send_markdown_message(text, channel=os.getenv("GENERAL_CHANNEL_ID"))


def notify_requester_about_new_vacation_status(vacation):
    start_date = datetime.datetime.strptime(vacation["vacation_start_date"]["S"], VACATION_DATES_FORMATTING)
    end_date = datetime.datetime.strptime(vacation["vacation_end_date"]["S"], VACATION_DATES_FORMATTING)
    new_vacation_status = vacation["vacation_status"]["S"]
    text = f"Your requested *vacation* for the following dates:\n\n" \
           f"*{start_date.strftime(VACATION_DATES_FORMATTING_TO_DISPLAY)} - " \
           f"{end_date.strftime(VACATION_DATES_FORMATTING_TO_DISPLAY)}*\n\n" \
           f"was *{new_vacation_status.lower()}* "
    text += VACATION_STATUSES_RESPONSES_MAPPING[new_vacation_status]

    send_markdown_message(text, channel=decode_key(vacation["pk"]["S"]))


def notify_ceo_about_new_vacation(vacation):
    start_date = datetime.datetime.strptime(vacation["vacation_start_date"]["S"], VACATION_DATES_FORMATTING)
    end_date = datetime.datetime.strptime(vacation["vacation_end_date"]["S"], VACATION_DATES_FORMATTING)
    body = {
        "channel": os.getenv("CEO_ACCOUNT_ID"),
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"@{vacation['username']['S']} want to book a *vacation* for the following dates:\n\n"
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
                "block_id": generate_block_id_for_vacation_decision(vacation["pk"]["S"], vacation["sk"]["S"]),
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
    }
    requests.post(SEND_MESSAGE_URL, headers={"Authorization": f"Bearer {BOT_TOKEN}"}, json=body)


@logger.inject_lambda_context(log_event=True)
@uncaught_exceptions_handler
def process_vacations(event, _):
    for record in event["Records"]:
        if record["dynamodb"]["Keys"]["sk"]["S"].startswith("VACATION"):
            if (event_name := record["eventName"]) == "MODIFY":
                vacation = record["dynamodb"]["NewImage"]
                if (new_vacation_status := vacation["vacation_status"]["S"]) == "APPROVED":
                    notify_general_about_approved_vacation(vacation)
                elif new_vacation_status == "DECLINED":
                    delete_vacation_from_db(decode_key(vacation["pk"]["S"]), decode_key(vacation["sk"]["S"]))
                notify_requester_about_new_vacation_status(vacation)

            elif event_name == "INSERT":
                vacation = record["dynamodb"]["NewImage"]
                notify_ceo_about_new_vacation(vacation)
                send_markdown_message(
                    "Vacation has been sent for approval :stuck_out_tongue_winking_eye::+1:",
                    channel=decode_key(vacation["pk"]["S"])
                )
