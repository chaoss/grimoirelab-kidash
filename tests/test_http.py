# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2019 Bitergia
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
import unittest

import httpretty

from kidash.clients.http import HttpClient, HEADERS


KIBANA_URL = 'http://example.com/'


class TestHttpClient(unittest.TestCase):
    """Http client tests"""

    def test_initialization(self):
        """Test whether attributes are initialized"""

        client = HttpClient(KIBANA_URL)

        self.assertEqual(client.base_url, KIBANA_URL)
        self.assertIsNotNone(client.session)
        self.assertEqual(client.session.headers['kbn-xsrf'], HEADERS.get('kbn-xsrf'))
        self.assertEqual(client.session.headers['Content-Type'], HEADERS.get('Content-Type'))

    @httpretty.activate
    def test_fetch(self):
        """Test the method fetch"""

        output = '{"result": "success"}'

        httpretty.register_uri(httpretty.GET,
                               KIBANA_URL,
                               body=output,
                               status=200)

        client = HttpClient(KIBANA_URL)
        response = client.fetch(KIBANA_URL)
        self.assertDictEqual(response, json.loads(output))

    @httpretty.activate
    def test_delete(self):
        """Test the method delete"""

        output = '{"result": "success"}'

        httpretty.register_uri(httpretty.DELETE,
                               KIBANA_URL,
                               body=output,
                               status=200)

        client = HttpClient(KIBANA_URL)
        response = client.delete(KIBANA_URL)
        self.assertDictEqual(response, json.loads(output))

    @httpretty.activate
    def test_put(self):
        """Test the method put"""

        output = '{"result": "success"}'
        data = "abcdef"

        httpretty.register_uri(httpretty.PUT,
                               KIBANA_URL,
                               body=output,
                               status=200)

        client = HttpClient(KIBANA_URL)
        response = client.put(KIBANA_URL, data)
        self.assertDictEqual(response, json.loads(output))

    @httpretty.activate
    def test_post(self):
        """Test the method post"""

        output = '{"result": "success"}'
        data = "abcdef"
        params = {"param1": 1, "param2": 2}

        httpretty.register_uri(httpretty.POST,
                               KIBANA_URL,
                               body=output,
                               status=200)

        client = HttpClient(KIBANA_URL)
        response = client.post(KIBANA_URL, data, params)
        self.assertDictEqual(response, json.loads(output))


if __name__ == "__main__":
    unittest.main(warnings='ignore')
