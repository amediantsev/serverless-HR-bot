from enum import Enum
import os
from uuid import uuid4
from datetime import datetime

import boto3
from boto3.dynamodb.conditions import Key

from exceptions import ValidationError
from slack.channels import get_channel_members
from slack.users import get_bot_user_id

dynamodb = boto3.resource("dynamodb")
USER_VACATION_TABLE = dynamodb.Table(os.getenv("USER_VACATION_TABLE_NAME"))


class EntityType(Enum):
    USER = "USER"
    VACATION = "VACATION"
    DECISION_MAKER = "DECISION_MAKER"
    CHANNEL = "CHANNEL"
    VACATIONS_NOTIFICATIONS_CHANNEL = "VACATIONS_NOTIFICATIONS_CHANNEL"


def generate_key(entity_type, name=None):
    key = f"{entity_type}#"
    if name:
        key += name
    return key


def format_vacation_string_to_date(string_date):
    return datetime.strptime(string_date, "%Y-%m-%d")


def validate_new_vacation(new_vacation_start_date, new_vacation_end_date, existing_user_vacations):
    new_vacation_start_date = format_vacation_string_to_date(new_vacation_start_date)
    new_vacation_end_date = format_vacation_string_to_date(new_vacation_end_date)
    if new_vacation_start_date > new_vacation_end_date:
        raise ValidationError("Start date cannot be later then end date")

    for vacation in existing_user_vacations:
        existing_vacation_start_date = format_vacation_string_to_date(vacation["vacation_start_date"])
        existing_vacation_end_date = format_vacation_string_to_date(vacation["vacation_end_date"])
        if (
            existing_vacation_end_date >= new_vacation_start_date
            and existing_vacation_start_date <= new_vacation_end_date
        ):
            raise ValidationError("Booked vacation intersect with already existing vacation")


def save_vacation_to_db(user_id, vacation_start_date, vacation_end_date, vacation_status="PENDING"):
    existing_user_vacations = get_user_vacations_from_db(user_id)
    validate_new_vacation(vacation_start_date, vacation_end_date, existing_user_vacations)

    vacation_id = str(uuid4())
    return USER_VACATION_TABLE.put_item(
        Item={
            "pk": generate_key(EntityType.USER.value, user_id),
            "sk": generate_key(EntityType.VACATION.value, vacation_id),
            "user_id": user_id,
            "vacation_id": vacation_id,
            "vacation_start_date": vacation_start_date,
            "vacation_end_date": vacation_end_date,
            "vacation_status": vacation_status
        }
    )


def get_user_vacations_from_db(user_id):
    return USER_VACATION_TABLE.query(
        KeyConditionExpression=(
            Key("pk").eq(generate_key(EntityType.USER.value, user_id))
            & Key("sk").begins_with(EntityType.VACATION.value)
        )
    ).get("Items", {})


def get_vacation_from_db(user_id, vacation_id):
    return USER_VACATION_TABLE.get_item(
        Key={
            "pk": generate_key(EntityType.USER.value, user_id),
            "sk": generate_key(EntityType.VACATION.value, vacation_id)
        }
    ).get("Item") or {}


def update_vacation_status(user_id, vacation_id, status):
    return USER_VACATION_TABLE.update_item(
        Key={
            "pk": generate_key(EntityType.USER.value, user_id),
            "sk": generate_key(EntityType.VACATION.value, vacation_id)
        },
        AttributeUpdates={"vacation_status": {"Value": status, "Action": "PUT"}}
    )


def delete_vacation_from_db(user_id, vacation_id):
    return USER_VACATION_TABLE.delete_item(
        Key={
            "pk": generate_key(EntityType.USER.value, user_id),
            "sk": generate_key(EntityType.VACATION.value, vacation_id)
        }
    )


def save_decision_maker_to_db(user_id):
    key = generate_key(EntityType.DECISION_MAKER.value)
    return USER_VACATION_TABLE.put_item(Item={"pk": key, "sk": key, "user_id": user_id})


def get_decision_maker_from_db():
    key = generate_key(EntityType.DECISION_MAKER.value)
    return USER_VACATION_TABLE.get_item(Key={"pk": key, "sk": key}).get("Item") or {}


def save_notifications_channel_to_db(channel_id):
    if get_bot_user_id() not in get_channel_members(channel_id):
        raise ValidationError(
            "HR Bot is not it the selected channel for notifications. Please, add him to the channel and try again."
        )
    key = generate_key(EntityType.VACATIONS_NOTIFICATIONS_CHANNEL.value)
    return USER_VACATION_TABLE.put_item(Item={"pk": key, "sk": key, "channel_id": channel_id})


def get_notifications_channel_from_db():
    key = generate_key(EntityType.VACATIONS_NOTIFICATIONS_CHANNEL.value)
    return USER_VACATION_TABLE.get_item(Key={"pk": key, "sk": key}).get("Item") or {}
