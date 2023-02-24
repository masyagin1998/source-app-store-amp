#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#
import random
import re
from copy import deepcopy
from datetime import datetime
from time import sleep
from typing import Any, Iterable, List, Mapping, MutableMapping, Tuple, Optional

import requests
from airbyte_cdk import AirbyteLogger
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.sources.streams.http import HttpStream
from airbyte_cdk.sources.streams.http.auth import NoAuth

from source_app_store_amp.user_agents import USER_AGENTS

URL_BASE = "https://amp-api.apps.apple.com"

ALL_COUNTRIES = ['ad', 'ae', 'af', 'ag', 'ai', 'al', 'am', 'an', 'ao', 'aq', 'ar', 'as', 'at', 'au', 'aw', 'ax', 'az', 'ba', 'bb', 'bd',
                 'be', 'bf', 'bg', 'bh', 'bi', 'bj', 'bl', 'bm', 'bn', 'bo', 'br', 'bs', 'bt', 'bv', 'bw', 'by', 'bz', 'ca', 'cc', 'cd',
                 'cf', 'cg', 'ch', 'ci', 'ck', 'cl', 'cm', 'cn', 'co', 'cr', 'cu', 'cv', 'cx', 'cy', 'cz', 'de', 'dj', 'dk', 'dm', 'do',
                 'dz', 'ec', 'ee', 'eg', 'eh', 'er', 'es', 'et', 'fi', 'fj', 'fk', 'fm', 'fo', 'fr', 'ga', 'gb', 'gd', 'ge', 'gf', 'gg',
                 'gh', 'gi', 'gl', 'gm', 'gn', 'gp', 'gq', 'gr', 'gs', 'gt', 'gu', 'gw', 'gy', 'hk', 'hm', 'hn', 'hr', 'ht', 'hu', 'id',
                 'ie', 'il', 'im', 'in', 'io', 'iq', 'ir', 'is', 'it', 'je', 'jm', 'jo', 'jp', 'ke', 'kg', 'kh', 'ki', 'km', 'kn', 'kp',
                 'kr', 'kw', 'ky', 'kz', 'la', 'lb', 'lc', 'li', 'lk', 'lr', 'ls', 'lt', 'lu', 'lv', 'ly', 'ma', 'mc', 'md', 'me', 'mf',
                 'mg', 'mh', 'mk', 'ml', 'mm', 'mn', 'mo', 'mp', 'mq', 'mr', 'ms', 'mt', 'mu', 'mv', 'mw', 'mx', 'my', 'mz', 'na', 'nc',
                 'ne', 'nf', 'ng', 'ni', 'nl', 'no', 'np', 'nr', 'nu', 'nz', 'om', 'pa', 'pe', 'pf', 'pg', 'ph', 'pk', 'pl', 'pm', 'pn',
                 'pr', 'ps', 'pt', 'pw', 'py', 'qa', 're', 'ro', 'rs', 'ru', 'rw', 'sa', 'sb', 'sc', 'sd', 'se', 'sg', 'sh', 'si', 'sj',
                 'sk', 'sl', 'sm', 'sn', 'so', 'sr', 'st', 'sv', 'sy', 'sz', 'tc', 'td', 'tf', 'tg', 'th', 'tj', 'tk', 'tl', 'tm', 'tn',
                 'to', 'tr', 'tt', 'tv', 'tw', 'tz', 'ua', 'ug', 'um', 'us', 'uy', 'uz', 'va', 'vc', 've', 'vg', 'vi', 'vn', 'vu', 'wf',
                 'ws', 'ye', 'yt', 'za', 'zm', 'zw']


class Reviews(HttpStream):
    url_base = URL_BASE
    primary_key = 'id'

    @staticmethod
    def __datetime_to_str(d: datetime) -> str:
        return d.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def __str_to_datetime(d: str) -> datetime:
        return datetime.strptime(d, "%Y-%m-%dT%H:%M:%SZ")

    def __get_token(self):
        resp = requests.get(self.__url)
        tags = resp.text.splitlines()
        for tag in tags:
            if re.match(r"<meta.+web-experience-app/config/environment", tag):
                token = re.search(r"token%22%3A%22(.+?)%22", tag).group(1)
                return f"bearer {token}"
        return ""

    def __update_params(self):
        self.__request_offset = 0
        self.__base_landing_url = "https://apps.apple.com"
        self.__url = self.__base_landing_url + "/{}/app/{}/id{}".format(
            self.__countries[self.__country_ind], self.__config['app_name'], self.__config['app_id'])
        self.__token = self.__get_token()

    # noinspection PyUnusedLocal
    def __init__(self, config, **kwargs):
        super().__init__()
        self.__config = config

        self.__logger = AirbyteLogger()

        self.__country_ind = 0
        self.__countries = self.__config['countries']['selected']

        self.__count = 0
        self.__total_count = 0

        self.__request_offset = 0
        self.__base_landing_url = ""
        self.__url = ""
        self.__token = ""
        self.__update_params()

        self.__cursor_value = datetime.strptime(self.__config['start_date'], "%Y-%m-%d")

        self.__logger.info("Read latest review timestamp from config: {}".format(self.__datetime_to_str(self.__cursor_value)))

    def read_records(self, *args, **kwargs) -> Iterable[Mapping[str, Any]]:
        for record in super().read_records(*args, **kwargs):
            yield record

    http_method = 'GET'

    raise_on_http_errors = False
    max_retries = 15
    retry_factor = 10.0

    def path(self, *, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None,
             next_page_token: Mapping[str, Any] = None, ) -> str:
        return "/v1/catalog/{}/apps/{}/reviews".format(self.__countries[self.__country_ind], self.__config['app_id'])

    def request_params(self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, Any] = None,
                       next_page_token: Mapping[str, Any] = None, ) -> MutableMapping[str, Any]:
        limit = self.__config.get('max_reviews_per_request', 20)
        return {
            'l': 'en-GB',
            'offset': self.__request_offset,
            'limit': limit, 'platform': "web",
            'additionalPlatforms': "appletv,ipad,iphone,mac"
        }

    def request_headers(self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, Any] = None,
                        next_page_token: Mapping[str, Any] = None) -> Mapping[str, Any]:
        return {
            'Accept': 'application/json',
            'Authorization': self.__token,
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': self.__base_landing_url,
            'Referer': self.__url,
            'User-Agent': random.choice(USER_AGENTS)
        }

    @staticmethod
    def __fetch_reviews(response: requests.Response):
        try:
            return response.json()['data']
        except Exception:
            return []

    def parse_response(self, response: requests.Response, *, stream_state: Mapping[str, Any], stream_slice: Mapping[str, Any] = None,
                       next_page_token: Mapping[str, Any] = None, ) -> Iterable[Mapping]:
        result = []

        reviews = self.__fetch_reviews(response)
        for review in reviews:
            if 'attributes' not in review:
                review['attributes'] = {}
            review['attributes']['country'] = self.__countries[self.__country_ind]

            cfv = review.get('attributes', {}).get('date')
            if (cfv is None) or (self.__str_to_datetime(cfv) > self.__cursor_value):
                result.append(review)

        self.__count += len(result)

        return result

    @staticmethod
    def __fetch_next_page_token(response: requests.Response):
        try:
            return response.json().get('next')
        except Exception:
            return None

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        timeout_ms = self.__config.get('timeout_milliseconds', 10000)
        sleep(timeout_ms / 1000.0)

        self.__request_offset = self.__fetch_next_page_token(response)

        token = "token"

        if self.__request_offset is not None:
            self.__request_offset = re.search("^.+offset=([0-9]+).*$", self.__request_offset).group(1)
            self.__request_offset = int(self.__request_offset)
        if self.__request_offset is None:
            self.__logger.info("Fetched {} reviews for country=\"{}\"".format(self.__count, self.__countries[self.__country_ind]))
            self.__country_ind += 1
            if self.__country_ind == len(self.__countries):
                self.__logger.info("Totally fetched {} reviews".format(self.__total_count + self.__count))
                token = None
            else:
                self.__update_params()

            self.__total_count += self.__count
            self.__count = 0
        return token

    def should_retry(self, response: requests.Response) -> bool:
        if response.status_code == 401:
            response.status_code = 200
            self.__logger.info("Changed {} response status code to {} to ignore error".format(401, 200))
        return (response.status_code == 401) or (response.status_code == 429) or (500 <= response.status_code < 600)


class SourceAppStoreAmp(AbstractSource):
    @staticmethod
    def __transform_config(config: Mapping[str, Any]) -> Mapping[str, Any]:
        if config['countries']['type'] == 'all':
            config = dict(deepcopy(config))
            config['countries']['type'] = 'selected'
            config['countries']['selected'] = ALL_COUNTRIES
        return config

    def check_connection(self, logger, config) -> Tuple[bool, any]:
        logger.info("Checking connection configuration for app \"{}\"...".format(config['app_name']))

        logger.info("Checking \"app_id\" and \"app_name\"...")
        response = requests.get("https://apps.apple.com/app/{}/id{}".format(config['app_name'], config['app_id']))
        if not response.ok:
            error_text = "\"app_id\" {} or \"app_name\" \"{}\" are invalid!".format(config['app_id'], config['app_name'])
            logger.error(error_text)
            return False, {'key': 'app_id', 'value': config['app_id'], 'error_text': error_text}
        logger.info("\"app_id\" and \"app_name\" are valid")

        logger.info("Connection configuration is valid")
        return True, None

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        config = self.__transform_config(config)
        return [Reviews(config, authenticator=NoAuth())]
