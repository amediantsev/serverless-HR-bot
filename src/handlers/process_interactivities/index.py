import datetime
import json
from urllib import parse

from aws_lambda_powertools import Logger
import holidays

from decorators import uncaught_exceptions_handler
from exceptions import ValidationError
from slack.messages import send_message
from slack.views import open_modal_view
from slack.views import get_book_vacation_modal_view, get_see_user_vacations_modal_view
from aws.dynamodb import (
    save_vacation_to_db, get_user_vacations_from_db, get_user_from_db, get_vacation_from_db, update_vacation_status
)


logger = Logger(service="HR-slack-bot")

UA_HOLIDAYS = holidays.UA()
VACATION_DATES_FORMATTING = "%Y-%m-%d"
VACATION_DATES_FORMATTING_TO_DISPLAY = "%d.%m.%Y"

INTERACTIVITIES_GET_FUNCTIONS_MAPPING = {
    "book_vacation": get_book_vacation_modal_view,
    "see_user_vacations": get_see_user_vacations_modal_view,
}


def process_block_actions(payload):
    received_action = payload["actions"][0]
    if received_action["action_id"] not in {"approve_vacation", "decline_vacation"}:
        return
    block_id_dict = json.loads(received_action["block_id"])
    if block_id_dict["event"] != "vacation_decision":
        return
    user_id = block_id_dict["user_id"]
    vacation_id = block_id_dict["vacation_id"]
    vacation_item = get_vacation_from_db(user_id, vacation_id)
    if vacation_item["vacation_status"] != "PENDING":
        return
    new_status = received_action["value"]
    update_vacation_status(user_id, vacation_id, new_status)
    send_message(
        f"Vacation for @{vacation_item['username']} was {new_status.lower()} :ok_hand:",
        webhook_url=payload["response_url"]
    )


def process_view_submission(payload):
    view = payload.get("view")
    if (callback_id := view["callback_id"]) == "book_vacation":
        block_data = view["state"]["values"]["vacation_dates"]
        try:
            save_vacation_to_db(
                payload["user"]["id"],
                payload["user"]["username"],
                block_data["vacation_start_date"]["selected_date"],
                block_data["vacation_end_date"]["selected_date"],
            )
        except ValidationError as e:
            send_message(
                f"Vacation *was not booked*, because it is invalid: {e} :thinking_face:",
                channel=payload["user"]["id"]
            )

    elif callback_id == "see_user_vacations":
        block_data = view["state"]["values"]["user_selector"]
        send_user_vacations(payload["user"]["id"], block_data["user_selector"]["selected_user"])


PAYLOAD_PROCESSING_FUNCTIONS_MAPPING = {
    "block_actions": process_block_actions,
    "view_submission": process_view_submission
}


def compute_working_days_in_vacation(
        start_date: datetime.datetime, end_date: datetime.datetime, working_days_by_year_dict
) -> int:
    vacation_dates_range = [start_date + datetime.timedelta(days=x) for x in range(0, (end_date - start_date).days)]
    working_days_count = 0
    for date in vacation_dates_range:
        if not (date.weekday() > 4 or date.strftime(VACATION_DATES_FORMATTING) in UA_HOLIDAYS):
            working_days_count += 1

            if working_days_by_year_dict.get(date.year):
                working_days_by_year_dict[date.year] += 1
            else:
                working_days_by_year_dict[date.year] = 1

    return working_days_count


def send_user_vacations(requster_user_id, interesting_user_id):
    user = get_user_from_db(interesting_user_id)
    username = user["username"] if user else "Selected user"
    user_vacations = get_user_vacations_from_db(interesting_user_id)
    if not user_vacations:
        text = f"{username} doesn't have booked vacations :thinking_face:"
    else:
        user_vacations.sort(
            key=lambda vacation: datetime.datetime.strptime(vacation["vacation_start_date"], VACATION_DATES_FORMATTING)
        )
        text = f"*@{username}* booked vacations:\n\n"

        total_working_days = 0
        working_days_by_year_dict = {}

        for index, vacation in enumerate(user_vacations, 1):
            start_date = datetime.datetime.strptime(vacation["vacation_start_date"], VACATION_DATES_FORMATTING)
            end_date = datetime.datetime.strptime(vacation["vacation_end_date"], VACATION_DATES_FORMATTING)
            vacation_working_days = compute_working_days_in_vacation(start_date, end_date, working_days_by_year_dict)
            total_working_days += vacation_working_days

            text += f"*{index}. " \
                    f"{start_date.strftime(VACATION_DATES_FORMATTING_TO_DISPLAY)} - " \
                    f"{end_date.strftime(VACATION_DATES_FORMATTING_TO_DISPLAY)}*\t\t" \
                    f"({vacation_working_days} working days)\n\n"

        text += f"Total working days: *{total_working_days}*\n"
        for year, days in working_days_by_year_dict.items():
            text += f"\t*{days}* days in *{year}* year\n"

    send_message(text, channel=requster_user_id)


@logger.inject_lambda_context(log_event=True)
@uncaught_exceptions_handler
def process_interactivities(event, _):
    request_body_json = parse.parse_qs(event["body"])
    payload = json.loads(request_body_json["payload"][0])
    logger.info({"payload": payload})

    if interactivity_name := payload.get("callback_id"):
        get_modal_view_body_function = INTERACTIVITIES_GET_FUNCTIONS_MAPPING[interactivity_name]
        modal_view_body = get_modal_view_body_function()
        open_modal_view(payload["trigger_id"], modal_view_body)

    elif payload_type := payload.get("type"):
        PAYLOAD_PROCESSING_FUNCTIONS_MAPPING.get(payload_type, lambda *args: None)(payload)

    return {"statusCode": 200}
