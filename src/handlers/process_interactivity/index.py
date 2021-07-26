import os
from datetime import datetime, timedelta
import json
from http import HTTPStatus
from urllib import parse

from aws_lambda_powertools import Logger
import holidays

from decorators import uncaught_exceptions_handler
from exceptions import ValidationError
from slack.users import get_user
from slack.messages import send_message
from slack.views import (
    open_modal_view,
    get_book_vacation_modal_view,
    get_see_user_vacations_modal_view,
    get_configure_workspace_modal_view,
)
from aws.dynamodb import VacationsTable

VACATIONS_DB_TABLE = VacationsTable()


SERVICE_NAME = os.getenv("SERVICE_NAME")
logger = Logger(service=SERVICE_NAME)

UA_HOLIDAYS = holidays.UA()
VACATION_DATES_FORMATTING = "%Y-%m-%d"
VACATION_DATES_FORMATTING_TO_DISPLAY = "%d.%m.%Y"

INTERACTIVITY_GET_FUNCTIONS_MAPPING = {
    "book_vacation": get_book_vacation_modal_view,
    "see_user_vacations": get_see_user_vacations_modal_view,
    "configure_workspace": get_configure_workspace_modal_view,
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
    vacation_item = VACATIONS_DB_TABLE.get_vacation_from_db(user_id, vacation_id)
    if vacation_item["vacation_status"] != "PENDING":
        return
    new_status = received_action["value"]
    VACATIONS_DB_TABLE.update_vacation_status(user_id, vacation_id, new_status)
    send_message(
        f"Vacation for @{get_user(user_id)['name']} was {new_status.lower()} :ok_hand:",
        webhook_url=payload["response_url"],
    )


def process_book_vacation_submission(view, user_submitted_id):
    block_data = view["state"]["values"]["vacation_dates"]
    try:
        VACATIONS_DB_TABLE.save_vacation_to_db(
            user_submitted_id,
            block_data["vacation_start_date"]["selected_date"],
            block_data["vacation_end_date"]["selected_date"],
        )
    except ValidationError as e:
        send_message(
            f"Vacation *was not booked*, because it is invalid: {e} :thinking_face:", channel=user_submitted_id
        )


def process_configure_workspace_submission(view, user_submitted_id):
    submission_data = view["state"]["values"]
    VACATIONS_DB_TABLE.save_decision_maker_to_db(
        submission_data["vacations_decision_maker_selector"]["vacations_decision_maker_selector"]["selected_user"]
    )
    try:
        VACATIONS_DB_TABLE.save_notifications_channel_to_db(
            submission_data["approved_vacations_notifications_selector"][
                "approved_vacations_notifications_selector"][
                "selected_channel"]
        )
    except ValidationError as e:
        send_message(
            f"Notifications channel *was not updated*, because it is invalid: {e} :thinking_face:",
            channel=user_submitted_id
        )


def process_see_user_vacations_submission(view, user_submitted_id):
    send_user_vacations(user_submitted_id, view["state"]["values"]["user_selector"]["user_selector"]["selected_user"])


VIEW_SUBMISSIONS_PROCESSORS_MAPPING = {
    "book_vacation": process_book_vacation_submission,
    "configure_workspace": process_configure_workspace_submission,
    "see_user_vacations": process_see_user_vacations_submission
}


def process_view_submission(payload):
    view = payload.get("view")
    VIEW_SUBMISSIONS_PROCESSORS_MAPPING[view["callback_id"]](view, payload["user"]["id"])


PAYLOAD_PROCESSING_FUNCTIONS_MAPPING = {
    "block_actions": process_block_actions,
    "view_submission": process_view_submission,
}


def compute_working_days_in_vacation(
    start_date: datetime, end_date: datetime, working_days_by_year_dict
) -> int:
    vacation_dates_range = [
        start_date + timedelta(days=x)
        for x in range(0, (end_date - start_date + timedelta(days=1)).days)
    ]
    working_days_count = 0
    for date in vacation_dates_range:
        if not (date.weekday() > 4 or date.strftime(VACATION_DATES_FORMATTING) in UA_HOLIDAYS):
            working_days_count += 1

            if working_days_by_year_dict.get(date.year):
                working_days_by_year_dict[date.year] += 1
            else:
                working_days_by_year_dict[date.year] = 1

    return working_days_count


def send_user_vacations(requester_user_id, interesting_user_id):
    user = get_user(interesting_user_id)
    username = user["name"]
    user_vacations = VACATIONS_DB_TABLE.get_user_vacations_from_db(interesting_user_id)
    if not user_vacations:
        text = f"{username} doesn't have booked vacations :thinking_face:"
    else:
        user_vacations.sort(
            key=lambda vacation: datetime.strptime(vacation["vacation_start_date"], VACATION_DATES_FORMATTING)
        )
        text = f"*@{username}* booked vacations:\n\n"

        total_working_days = 0
        working_days_by_year_dict = {}

        for index, vacation in enumerate(user_vacations, 1):
            start_date = datetime.strptime(vacation["vacation_start_date"], VACATION_DATES_FORMATTING)
            end_date = datetime.strptime(vacation["vacation_end_date"], VACATION_DATES_FORMATTING)
            vacation_working_days = compute_working_days_in_vacation(start_date, end_date, working_days_by_year_dict)
            total_working_days += vacation_working_days

            text += (
                f"*{index}. "
                f"{start_date.strftime(VACATION_DATES_FORMATTING_TO_DISPLAY)} - "
                f"{end_date.strftime(VACATION_DATES_FORMATTING_TO_DISPLAY)}*\t\t"
                f"({vacation_working_days} working days)\n\n"
            )

        text += f"Total working days: *{total_working_days}*\n"
        for year, days in working_days_by_year_dict.items():
            text += f"\t*{days}* days in *{year}* year\n"

    send_message(text, channel=requester_user_id)


@logger.inject_lambda_context(log_event=True)
@uncaught_exceptions_handler
def process_interactivity(event, _):
    request_body_json = parse.parse_qs(event["body"])
    payload = json.loads(request_body_json["payload"][0])
    logger.info({"payload": payload})
    VACATIONS_DB_TABLE.workspace_id = payload["team"]["id"]

    if interactivity_name := payload.get("callback_id"):
        get_modal_view_body_function = INTERACTIVITY_GET_FUNCTIONS_MAPPING[interactivity_name]
        modal_view_body = get_modal_view_body_function()
        open_modal_view(payload["trigger_id"], modal_view_body)

    elif payload_type := payload.get("type"):
        payload_processor = PAYLOAD_PROCESSING_FUNCTIONS_MAPPING.get(payload_type, lambda *args: None)
        payload_processor(payload)

    return {"statusCode": HTTPStatus.OK}
