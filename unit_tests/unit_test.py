import json

import pytest
from airbyte_cdk.models import SyncMode
from jsonschema import validate

from source_app_store_amp.source import SourceAppStoreAmp

sample_config = {
    "app_name": "netschool",
    "app_id": "1529087012",
    "countries": {
        "type": "all"
    },
    "start_date": "2022-01-01",
    "timeout_milliseconds": 8000,
    "max_reviews_per_request": 20
}


@pytest.mark.parametrize(
    "config",
    [
        sample_config
    ],
)
def test_trustpilot_scraper_reviews_stream(config):
    reviews = SourceAppStoreAmp().streams(config)[0]
    record_schema = json.load(open("./source_app_store_amp/schemas/reviews.json"))
    for record in reviews.read_records(SyncMode.full_refresh):
        assert (validate(record, record_schema) is None)
