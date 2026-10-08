"""DynamoDB adapter — single table, `pk = kind`, `sk = id`, GSI `gsi1` for per-user listing.

Fine at hackathon scale; see docs/ARCHITECTURE.md for the production access-pattern notes.
"""
from __future__ import annotations

import json
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

from .base import Store, now_iso


def to_dynamo(o):
    return json.loads(json.dumps(o, default=str), parse_float=Decimal)


def from_dynamo(o):
    if isinstance(o, Decimal):
        return int(o) if o == o.to_integral_value() else float(o)
    if isinstance(o, list):
        return [from_dynamo(v) for v in o]
    if isinstance(o, dict):
        return {k: from_dynamo(v) for k, v in o.items()}
    return o


class DynamoStore(Store):
    name = "dynamodb"

    def __init__(self, table_name: str, region: str, resource=None) -> None:
        self.table_name = table_name
        self.table = (resource or boto3.resource("dynamodb", region_name=region)).Table(table_name)

    @staticmethod
    def _item(kind: str, id: str, doc: dict) -> dict:
        item = {"pk": kind, "sk": id, "doc": to_dynamo(doc), "updated_at": now_iso()}
        if doc.get("user_id"):
            item["gsi1pk"] = f"{kind}#{doc['user_id']}"
            item["gsi1sk"] = id
        return item

    def put(self, kind, id, doc):
        self.table.put_item(Item=self._item(kind, id, doc))
        return doc

    def put_many(self, items):
        with self.table.batch_writer(overwrite_by_pkeys=["pk", "sk"]) as bw:
            for kind, id, doc in items:
                bw.put_item(Item=self._item(kind, id, doc))

    def get(self, kind, id):
        r = self.table.get_item(Key={"pk": kind, "sk": id}).get("Item")
        return from_dynamo(r["doc"]) if r else None

    def list(self, kind, owner=None):
        if owner is not None:
            kwargs = {"IndexName": "gsi1", "KeyConditionExpression": Key("gsi1pk").eq(f"{kind}#{owner}")}
        else:
            kwargs = {"KeyConditionExpression": Key("pk").eq(kind)}
        rows: list[dict] = []
        while True:
            r = self.table.query(**kwargs)
            rows.extend(from_dynamo(i["doc"]) for i in r["Items"])
            if "LastEvaluatedKey" not in r:
                return rows
            kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]

    def delete(self, kind, id):
        self.table.delete_item(Key={"pk": kind, "sk": id})

    def is_empty(self):
        return not self.table.scan(Limit=1).get("Items")
