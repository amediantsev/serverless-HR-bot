from enum import Enum
import os
from uuid import uuid4
from datetime import datetime

import boto3
from boto3.dynamodb.conditions import Key

from exceptions import ValidationError


dynamodb = boto3.resource("dynamodb")
USER_VACATION_TABLE = dynamodb.Table(os.getenv("USER_VACATION_TABLE_NAME"))


class EntityType(Enum):
    USER = "USER"
    VACATION = "VACATION"


def generate_key(type, name):
    return f"{type}#{name}"


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


def save_vacation_to_db(user_id, username, vacation_start_date, vacation_end_date, vacation_status="PENDING"):
    save_user_to_db(user_id, username)
    existing_user_vacations = get_user_vacations_from_db(user_id)
    validate_new_vacation(vacation_start_date, vacation_end_date, existing_user_vacations)

    vacation_id = str(uuid4())
    pk = generate_key(EntityType.USER.value, user_id)
    sk = generate_key(EntityType.VACATION.value, vacation_id)
    response = USER_VACATION_TABLE.put_item(
        Item={
            "pk": pk,
            "sk": sk,
            "user_id": user_id,
            "vacation_id": vacation_id,
            "vacation_start_date": vacation_start_date,
            "vacation_end_date": vacation_end_date,
            "username": username,
            "vacation_status": vacation_status
        }
    )
    return response


def get_user_from_db(user_id):
    pk = sk = generate_key(EntityType.USER.value, user_id)
    user = USER_VACATION_TABLE.get_item(Key={"pk": pk, "sk": sk})
    return user.get("Item")


def save_user_to_db(user_id, username):
    pk = sk = generate_key(EntityType.USER.value, user_id)
    response = USER_VACATION_TABLE.put_item(Item={"pk": pk, "sk": sk, "user_id": user_id, "username": username})
    return response


def get_user_vacations_from_db(user_id):
    pk = generate_key(EntityType.USER.value, user_id)
    response = USER_VACATION_TABLE.query(
        KeyConditionExpression=Key("pk").eq(pk) & Key("sk").begins_with(EntityType.VACATION.value)
    )
    return response.get("Items")


def get_vacation_from_db(user_id, vacation_id):
    pk = generate_key(EntityType.USER.value, user_id)
    sk = generate_key(EntityType.VACATION.value, vacation_id)
    response = USER_VACATION_TABLE.get_item(Key={"pk": pk, "sk": sk})
    return response["Item"]


def update_vacation_status(user_id, vacation_id, status):
    pk = generate_key(EntityType.USER.value, user_id)
    sk = generate_key(EntityType.VACATION.value, vacation_id)
    response = USER_VACATION_TABLE.update_item(
        Key={"pk": pk, "sk": sk}, AttributeUpdates={"vacation_status": {"Value": status, "Action": "PUT"}}
    )
    return response


def delete_vacation_from_db(user_id, vacation_id):
    pk = generate_key(EntityType.USER.value, user_id)
    sk = generate_key(EntityType.VACATION.value, vacation_id)
    response = USER_VACATION_TABLE.delete_item(Key={"pk": pk, "sk": sk})
    return response
