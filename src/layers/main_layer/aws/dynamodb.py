from enum import Enum
import os
from uuid import uuid4
from datetime import datetime

import boto3
from boto3.dynamodb.conditions import Key

from exceptions import ValidationError, NotSpecifiedWorkspaceError


dynamodb = boto3.resource("dynamodb")
USER_VACATIONS_TABLE_NAME = os.getenv("USER_VACATIONS_TABLE_NAME")


class EntityType(Enum):
    USER = "USER"
    VACATION = "VACATION"
    DECISION_MAKER = "DECISION_MAKER"
    CHANNEL = "CHANNEL"
    VACATIONS_NOTIFICATIONS_CHANNEL = "VACATIONS_NOTIFICATIONS_CHANNEL"
    WORKSPACE = "WORKSPACE"


class VacationsTable:
    def __init__(self, *args, **kwargs):
        self._workspace_id = None
        self._table = dynamodb.Table(USER_VACATIONS_TABLE_NAME, *args, **kwargs)

    class _Decorators:
        @classmethod
        def crud_workspace_setting(cls, decorated_method):
            """
            Extends CRUD methods to use for some specific workspace.
            Check if workspace prefix (WORKSPACE#{workspace_id}) is specified for table object
            and insert it before each key.
            """
            def wrapper(self, **kwargs):
                if not self.workspace_id:
                    raise NotSpecifiedWorkspaceError()

                if decorated_method.__name__ == "_put_item":
                    item = kwargs.pop("Item", {})
                    for key in self._table.key_schema:
                        key_name = key["AttributeName"]
                        if current_key_value := item.get(key_name):
                            item[key_name] = f"{self._keys_prefix}#{current_key_value}"

                    item["workspace_id"] = self.workspace_id
                    kwargs["Item"] = item
                else:
                    keys_dict = kwargs.pop("Key", {})
                    update_keys_dict = {}
                    for key_name, key_value in keys_dict.items():
                        update_keys_dict[key_name] = f"{self._keys_prefix}#{key_value}"
                    kwargs["Key"] = update_keys_dict

                print(f"I'm invoking method {decorated_method.__name__} with kwargs: {kwargs}")
                return decorated_method(self, **kwargs)

            return wrapper

    @staticmethod
    def _generate_key(entity_type, name=None):
        key = f"{entity_type}#"
        if name:
            key += name
        return key

    @property
    def workspace_id(self):
        return self._workspace_id

    @workspace_id.setter
    def workspace_id(self, current_workspace_id):
        self._workspace_id = current_workspace_id
    
    @property
    def _keys_prefix(self):
        return self._generate_key(EntityType.WORKSPACE.value, self._workspace_id)

    @staticmethod
    def format_vacation_string_to_date(string_date):
        return datetime.strptime(string_date, "%Y-%m-%d")

    @_Decorators.crud_workspace_setting
    def _put_item(self, **kwargs):
        return self._table.put_item(**kwargs)

    @_Decorators.crud_workspace_setting
    def _get_item(self, **kwargs):
        print(kwargs)
        return self._table.get_item(**kwargs)

    @_Decorators.crud_workspace_setting
    def _update_item(self, **kwargs):
        return self._table.update_item(**kwargs)

    @_Decorators.crud_workspace_setting
    def _delete_item(self, **kwargs):
        return self._table.delete_item(**kwargs)

    def save_vacation(self, user_id, vacation_start_date, vacation_end_date, vacation_status="PENDING"):
        existing_user_vacations = self.get_vacations(user_id)

        new_vacation_start_date = self.format_vacation_string_to_date(vacation_start_date)
        new_vacation_end_date = self.format_vacation_string_to_date(vacation_end_date)
        if new_vacation_start_date > new_vacation_end_date:
            raise ValidationError("Start date cannot be later then end date")

        for vacation in existing_user_vacations:
            existing_vacation_start_date = self.format_vacation_string_to_date(vacation["vacation_start_date"])
            existing_vacation_end_date = self.format_vacation_string_to_date(vacation["vacation_end_date"])
            if (
                    existing_vacation_end_date >= new_vacation_start_date
                    and existing_vacation_start_date <= new_vacation_end_date
            ):
                raise ValidationError("Booked vacation intersect with already existing vacation")

        vacation_id = str(uuid4())
        return self._put_item(
            Item={
                "pk": self._generate_key(EntityType.USER.value, user_id),
                "sk": self._generate_key(EntityType.VACATION.value, vacation_id),
                "user_id": user_id,
                "vacation_id": vacation_id,
                "vacation_start_date": vacation_start_date,
                "vacation_end_date": vacation_end_date,
                "vacation_status": vacation_status
            }
        )

    def get_vacations(self, user_id):
        if not self.workspace_id:
            raise NotSpecifiedWorkspaceError()
        return self._table.query(
            KeyConditionExpression=(
                Key("pk").eq(f"{self._keys_prefix}#{self._generate_key(EntityType.USER.value, user_id)}")
                & Key("sk").begins_with(f"{self._keys_prefix}#{EntityType.VACATION.value}")
            )
        ).get("Items", {})

    def get_vacation(self, user_id, vacation_id):
        return self._get_item(
            Key={
                "pk": self._generate_key(EntityType.USER.value, user_id),
                "sk": self._generate_key(EntityType.VACATION.value, vacation_id)
            }
        ).get("Item") or {}

    def update_vacation_status(self, user_id, vacation_id, status):
        return self._update_item(
            Key={
                "pk": self._generate_key(EntityType.USER.value, user_id),
                "sk": self._generate_key(EntityType.VACATION.value, vacation_id)
            },
            UpdateExpression="SET vacation_status = :new_vacation_status",
            ExpressionAttributeValues={":new_vacation_status": status},
        )

    def delete_vacation(self, user_id, vacation_id):
        return self._delete_item(
            Key={
                "pk": self._generate_key(EntityType.USER.value, user_id),
                "sk": self._generate_key(EntityType.VACATION.value, vacation_id)
            }
        )

    def save_decision_maker(self, user_id):
        key = self._generate_key(EntityType.DECISION_MAKER.value)
        return self._put_item(Item={"pk": key, "sk": key, "user_id": user_id})

    def get_decision_maker(self):
        key = self._generate_key(EntityType.DECISION_MAKER.value)
        return self._get_item(Key={"pk": key, "sk": key}).get("Item") or {}

    def save_notifications_channel(self, channel_id):
        if not self.workspace_id:
            raise NotSpecifiedWorkspaceError()
        key = self._generate_key(EntityType.VACATIONS_NOTIFICATIONS_CHANNEL.value)
        return self._put_item(Item={"pk": key, "sk": key, "channel_id": channel_id})

    def get_notifications_channel(self):
        key = self._generate_key(EntityType.VACATIONS_NOTIFICATIONS_CHANNEL.value)
        return self._get_item(Key={"pk": key, "sk": key}).get("Item") or {}

    def save_workspace(self, workspace_id, access_token):
        key = self._generate_key(EntityType.WORKSPACE.value, workspace_id)
        return self._table.put_item(
            Item={"pk": key, "sk": key, "workspace_id": workspace_id, "access_token": access_token}
        )

    def get_workspace(self, workspace_id):
        key = self._generate_key(EntityType.WORKSPACE.value, workspace_id)
        return self._table.get_item(Key={"pk": key, "sk": key}).get("Item") or {}
