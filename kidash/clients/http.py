# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2020 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Authors:
#   Valerio Cosentino <valcos@bitergia.com>
#

import json

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


HEADERS = {
    "Content-Type": "application/json",
    "kbn-xsrf": "true"
}

SLEEP_TIME = 1
MAX_RETRIES = 5

VERIFY = False


class HttpClient:
    """Abstract class for HTTP clients.

    Base class to interact with the Dashboard and SavedObjects APIs.
    It takes care of retrying requests in case connection issues. If
    Kibana does not send back a response after retrying a request,
    a RetryError exception is thrown.

    :param base_url: base URL of the Kibana instance
    """

    def __init__(self, base_url):
        self.base_url = base_url
        self.session = self._create_http_session()

    def __del__(self):
        self._close_http_session()

    def fetch(self, url, params=None, headers=None):
        """Fetch the data from a given URL.

        :param url: link to the resource
        :param params: params of the request
        :param headers: headers of the request

        :returns a response object
        """
        response = self.session.get(url, params=params, headers=headers, verify=VERIFY)
        response.raise_for_status()

        return response.json()

    def delete(self, url, headers=None):
        """Delete the target object pointed by the url.

        :param url: link to the resource
        :param headers: headers of the request

        :returns a response object
        """
        response = self.session.delete(url, headers=headers, verify=VERIFY)
        response.raise_for_status()

        return response.json()

    def put(self, url, data, headers=None):
        """Update the target object pointed by the url.

        :param url: link to the resource
        :param data: data to upload
        :param headers: headers of the request

        :returns a response object
        """
        response = self.session.put(url, data=json.dumps(data), headers=headers, verify=VERIFY)
        response.raise_for_status()

        return response.json()

    def post(self, url, data, params, headers=None):
        """Update the target object pointed by the url.

        :param url: link to the resource
        :param data: data to upload
        :param params: params of the request
        :param headers: headers of the request

        :returns a response object
        """
        response = self.session.post(url, params=params, data=json.dumps(data), headers=headers, verify=VERIFY)
        response.raise_for_status()

        return response.json()

    def _create_http_session(self):
        """Create a http session and initialize the retry object."""

        session = requests.Session()
        session.headers.update(HEADERS)

        retries = urllib3.util.Retry(total=MAX_RETRIES,
                                     backoff_factor=SLEEP_TIME)

        session.mount('http://', requests.adapters.HTTPAdapter(max_retries=retries))
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=retries))

        return session

    def _close_http_session(self):
        """Close the http session."""

        if self.session:
            self.session.keep_alive = False
