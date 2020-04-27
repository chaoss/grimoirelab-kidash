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
import os
import unittest

import httpretty
import requests

from kidash.clients.http import HEADERS
from kidash.clients.saved_objects import (logger,
                                          SavedObjects)


KIBANA_URL = 'http://example.com/'
SAVED_OBJECTS_URL = KIBANA_URL + SavedObjects.API_SAVED_OBJECTS_URL

OBJECT_TYPE = "index-pattern"
OBJECT_ID = "7c2496c0-b013-11e8-8771-a349686d998a"
OBJECT_URL = KIBANA_URL + SavedObjects.API_SAVED_OBJECTS_URL + "/" + OBJECT_TYPE + "/" + OBJECT_ID


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


class TestSavedObjects(unittest.TestCase):
    """SavedObjects API tests"""

    def test_initialization(self):
        """Test whether attributes are initialized"""

        client = SavedObjects(KIBANA_URL)

        self.assertEqual(client.base_url, KIBANA_URL)
        self.assertIsNotNone(client.session)
        self.assertEqual(client.session.headers['kbn-xsrf'], HEADERS.get('kbn-xsrf'))
        self.assertEqual(client.session.headers['Content-Type'], HEADERS.get('Content-Type'))

    @httpretty.activate
    def test_fetch_objs(self):
        """Test whether objects are correctly returned by the method fetch_objs"""

        saved_objs_page_1 = read_file('data/objects_1')
        saved_objs_page_2 = read_file('data/objects_2')
        saved_objs_page_3 = read_file('data/objects_empty')

        httpretty.register_uri(httpretty.GET,
                               SAVED_OBJECTS_URL + '?page=3',
                               body=saved_objs_page_3,
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               SAVED_OBJECTS_URL + '?page=2',
                               body=saved_objs_page_2,
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               SAVED_OBJECTS_URL + '?page=1',
                               body=saved_objs_page_1,
                               status=200)

        client = SavedObjects(KIBANA_URL)
        fetched_objs = [obj for page_objs in client.fetch_objs(SAVED_OBJECTS_URL) for obj in page_objs]
        self.assertEqual(len(fetched_objs), 4)

        obj = fetched_objs[0]
        self.assertEqual(obj['id'], "0b84fff0-b1b6-11e8-8aac-ef7fd4d8cbad")
        self.assertEqual(obj['type'], "visualization")
        self.assertEqual(obj["version"], 1)

        obj = fetched_objs[1]
        self.assertEqual(obj['id'], "00cf9cf0-d074-11e8-8aac-ef7fd4d8cbad")
        self.assertEqual(obj['type'], "visualization")
        self.assertEqual(obj["version"], 1)

        obj = fetched_objs[2]
        self.assertEqual(obj['id'], "1a23fbd0-bc0e-11e8-8aac-ef7fd4d8cbad")
        self.assertEqual(obj['type'], "visualization")
        self.assertEqual(obj["version"], 2)

        obj = fetched_objs[3]
        self.assertEqual(obj['id'], "00fee5a0-7eb7-11e8-a4e7-6b1c6a13c58d")
        self.assertEqual(obj['type'], "visualization")
        self.assertEqual(obj["version"], 1)

    @httpretty.activate
    def test_fetch_objs_empty(self):
        """Test whether no objects are returned by the method fetch_objs"""

        saved_objs_empty = read_file('data/objects_empty')

        httpretty.register_uri(httpretty.GET,
                               SAVED_OBJECTS_URL + '?page=1',
                               body=saved_objs_empty,
                               status=200)

        client = SavedObjects(KIBANA_URL)
        fetched_objs = [obj for page_objs in client.fetch_objs(SAVED_OBJECTS_URL) for obj in page_objs]
        self.assertEqual(len(fetched_objs), 0)

    @httpretty.activate
    def test_fetch_objs_internal_error(self):
        """Test whether a log error message is thrown when an internal error occurs with the method fetch_objs"""

        saved_objs_error = read_file('data/objects_error')
        saved_objs_empty = read_file('data/objects_empty')

        httpretty.register_uri(httpretty.GET,
                               SAVED_OBJECTS_URL + '?page=2',
                               body=saved_objs_empty,
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               SAVED_OBJECTS_URL + '?page=1',
                               body=saved_objs_error,
                               status=200)

        client = SavedObjects(KIBANA_URL)
        with self.assertLogs(logger, level='ERROR') as cm:
            _ = [obj for page_objs in client.fetch_objs(SAVED_OBJECTS_URL) for obj in page_objs]
            self.assertEqual(cm.output[0],
                             'ERROR:kidash.clients.saved_objects:Impossible to retrieve objects at page 1, '
                             'url http://example.com/api/saved_objects, An internal server error occurred')

    @httpretty.activate
    def test_fetch_objs_http_error(self):
        """Test whether an exception is thrown when the HTTP error is not 500"""

        saved_objs_page = read_file('data/objects_1')

        httpretty.register_uri(httpretty.GET,
                               SAVED_OBJECTS_URL,
                               body=saved_objs_page,
                               status=404)

        client = SavedObjects(KIBANA_URL)
        with self.assertRaises(requests.exceptions.HTTPError):
            _ = [obj for page_objs in client.fetch_objs(SAVED_OBJECTS_URL) for obj in page_objs]

    @httpretty.activate
    def test_fetch_objs_http_error_500(self):
        """Test whether a warning is logged when a 500 HTTP error occurs"""

        saved_objs_page_1 = read_file('data/objects_1')
        saved_objs_page_2 = read_file('data/objects_2')
        saved_objs_page_3 = read_file('data/objects_empty')

        httpretty.register_uri(httpretty.GET,
                               SAVED_OBJECTS_URL + '?page=3',
                               body=saved_objs_page_3,
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               SAVED_OBJECTS_URL + '?page=2',
                               body=saved_objs_page_2,
                               status=500)

        httpretty.register_uri(httpretty.GET,
                               SAVED_OBJECTS_URL + '?page=1',
                               body=saved_objs_page_1,
                               status=200)

        client = SavedObjects(KIBANA_URL)
        with self.assertLogs(logger) as cm:
            _ = [obj for page_objs in client.fetch_objs(SAVED_OBJECTS_URL) for obj in page_objs]

        self.assertEqual(cm.output[0],
                         'WARNING:kidash.clients.saved_objects:Impossible to retrieve object at page 2, '
                         'url http://example.com/api/saved_objects')

    @httpretty.activate
    def test_get_object(self):
        """Test the method get_object"""

        obj_data = read_file('data/object_index-pattern')

        httpretty.register_uri(httpretty.GET,
                               OBJECT_URL,
                               body=obj_data,
                               status=200)

        client = SavedObjects(KIBANA_URL)
        obj = client.get_object(OBJECT_TYPE, OBJECT_ID)
        self.assertDictEqual(obj, json.loads(obj_data))

    @httpretty.activate
    def test_get_object_not_found(self):
        """Test whether a warning is logged when the object is not found"""

        obj_data = read_file('data/object_index-pattern')

        httpretty.register_uri(httpretty.GET,
                               OBJECT_URL,
                               body=obj_data,
                               status=404)

        client = SavedObjects(KIBANA_URL)
        with self.assertLogs(logger, level='WARNING') as cm:
            obj = client.get_object(OBJECT_TYPE, OBJECT_ID)
            self.assertEqual(cm.output[0],
                             'WARNING:kidash.clients.saved_objects:'
                             'No ' + OBJECT_TYPE + ' found with id: ' + OBJECT_ID)
            self.assertIsNone(obj)

    @httpretty.activate
    def test_get_object_http_error(self):
        """Test whether an exception is thrown when the HTTP error is not 404"""

        obj_data = read_file('data/object_index-pattern')

        httpretty.register_uri(httpretty.GET,
                               OBJECT_URL,
                               body=obj_data,
                               status=500)

        client = SavedObjects(KIBANA_URL)
        with self.assertRaises(requests.exceptions.HTTPError):
            _ = client.get_object(OBJECT_TYPE, OBJECT_ID)

    @httpretty.activate
    def test_delete_object(self):
        """Test the method delete_object"""

        httpretty.register_uri(httpretty.DELETE,
                               OBJECT_URL,
                               body="{}",
                               status=200)

        client = SavedObjects(KIBANA_URL)
        with self.assertLogs(logger, level='INFO') as cm:
            _ = client.delete_object(OBJECT_TYPE, OBJECT_ID)
            self.assertEqual(cm.output[0],
                             'INFO:kidash.clients.saved_objects:'
                             'Object ' + OBJECT_TYPE + ' with id ' + OBJECT_ID + ' deleted')

    @httpretty.activate
    def test_delete_object_not_found(self):
        """Test whether a warning is logged when the object is not found"""

        obj_data = read_file('data/object_index-pattern')

        httpretty.register_uri(httpretty.DELETE,
                               OBJECT_URL,
                               body=obj_data,
                               status=404)

        client = SavedObjects(KIBANA_URL)
        with self.assertLogs(logger, level='WARNING') as cm:
            obj = client.delete_object(OBJECT_TYPE, OBJECT_ID)
            self.assertEqual(cm.output[0],
                             'WARNING:kidash.clients.saved_objects:'
                             'No ' + OBJECT_TYPE + ' found with id: ' + OBJECT_ID)
            self.assertIsNone(obj)

    @httpretty.activate
    def test_delete_object_http_error(self):
        """Test whether an exception is thrown when the HTTP error is not 404"""

        obj_data = read_file('data/object_index-pattern')

        httpretty.register_uri(httpretty.DELETE,
                               OBJECT_URL,
                               body=obj_data,
                               status=500)

        client = SavedObjects(KIBANA_URL)
        with self.assertRaises(requests.exceptions.HTTPError):
            _ = client.delete_object(OBJECT_TYPE, OBJECT_ID)

    @httpretty.activate
    def test_update_object(self):
        """Test the method update_object"""

        obj_data = read_file('data/object_index-pattern')
        attributes = {
            "version": "2"
        }

        httpretty.register_uri(httpretty.PUT,
                               OBJECT_URL,
                               body=obj_data,
                               status=200)

        client = SavedObjects(KIBANA_URL)
        with self.assertLogs(logger, level='INFO') as cm:
            obj = client.update_object(OBJECT_TYPE, OBJECT_ID, attributes)
            self.assertEqual(cm.output[0],
                             'INFO:kidash.clients.saved_objects:'
                             'Object ' + OBJECT_TYPE + ' with id ' + OBJECT_ID + ' updated')
            self.assertDictEqual(obj, json.loads(obj_data))

    @httpretty.activate
    def test_update_object_not_found(self):
        """Test whether a warning is logged when the object is not found"""

        obj_data = read_file('data/object_index-pattern')
        attributes = {
            "version": "2"
        }

        httpretty.register_uri(httpretty.PUT,
                               OBJECT_URL,
                               body=obj_data,
                               status=404)

        client = SavedObjects(KIBANA_URL)
        with self.assertLogs(logger, level='WARNING') as cm:
            obj = client.update_object(OBJECT_TYPE, OBJECT_ID, attributes)
            self.assertEqual(cm.output[0],
                             'WARNING:kidash.clients.saved_objects:'
                             'No ' + OBJECT_TYPE + ' found with id: ' + OBJECT_ID)
            self.assertIsNone(obj)

    @httpretty.activate
    def test_update_object_not_updated(self):
        """Test whether a warning is logged when the object is not updated"""

        obj_data = read_file('data/object_index-pattern')
        attributes = {
            "version": "2"
        }

        httpretty.register_uri(httpretty.PUT,
                               OBJECT_URL,
                               body=obj_data,
                               status=400)

        client = SavedObjects(KIBANA_URL)
        with self.assertLogs(logger, level='WARNING') as cm:
            obj = client.update_object(OBJECT_TYPE, OBJECT_ID, attributes)
            self.assertEqual(cm.output[0], 'WARNING:kidash.clients.saved_objects:Impossible to update '
                                           'attributes ' + json.dumps(attributes, sort_keys=True) +
                                           ' for ' + OBJECT_TYPE + ' with id ' + OBJECT_ID)
            self.assertIsNone(obj)

    @httpretty.activate
    def test_update_object_http_error(self):
        """Test whether an exception is thrown when the HTTP error is not 404 or 400"""

        obj_data = read_file('data/object_index-pattern')
        attributes = {
            "version": "2"
        }

        httpretty.register_uri(httpretty.PUT,
                               OBJECT_URL,
                               body=obj_data,
                               status=500)

        client = SavedObjects(KIBANA_URL)
        with self.assertRaises(requests.exceptions.HTTPError):
            _ = client.update_object(OBJECT_TYPE, OBJECT_ID, attributes)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
