#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Import and Export Kibana dashboards
#
# Copyright (C) 2015 Bitergia
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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Authors:
#   Valerio Cosentino <valcos@bitergia.com>
#

import logging
import json
import pkgutil
import requests


from grimoirelab_toolkit.uris import urijoin


DEBUG_LOG_FORMAT = "[%(asctime)s - %(name)s - %(levelname)s] - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=DEBUG_LOG_FORMAT)


HEADERS = {
    "Content-Type": "application/json",
    "kbn-xsrf": "true"
}

DASHBOARD = "dashboard"
SEARCH = "search"
VISUALIZATION = "visualization"
INDEX_PATTERN = "index-pattern"


class KibanaClient:

    @staticmethod
    def fetch(url, params=None, headers=HEADERS):
        """Fetch the data from a given URL.

        :param url: link to the resource
        :param params: params of the request
        :param headers: headers of the request

        :returns a response object
        """
        response = requests.get(url, params=params, headers=headers)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            raise error

        return response.json()

    @staticmethod
    def delete(url, headers=HEADERS):
        """Delete the target object pointed by the url.

        :param url: link to the resource
        :param headers: headers of the request

        :returns a response object
        """
        response = requests.delete(url, headers=headers)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            raise error

        return response.json()

    @staticmethod
    def put(url, data, headers=HEADERS):
        """Update the target object pointed by the url.

        :param url: link to the resource
        :param data: data to upload
        :param headers: headers of the request

        :returns a response object
        """
        response = requests.put(url, data=json.dumps(data), headers=headers)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            raise error

        return response.json()

    @staticmethod
    def post(url, data, params, headers=HEADERS):
        """Update the target object pointed by the url.

        :param url: link to the resource
        :param data: data to upload
        :param params: params of the request
        :param headers: headers of the request

        :returns a response object
        """
        response = requests.post(url, params=params, data=json.dumps(data), headers=headers)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            raise error

        return response.json()


class SavedObjects(KibanaClient):

    API_SAVED_OBJECTS_URL = 'api/saved_objects'
    API_SEARCH_COMMAND = '_search'

    def __init__(self, base_url):
        self.base_url = base_url

    def find_by_title(self, obj_type, obj_title):
        """Find an object by its type and title.

        :param obj_type: type of the target object
        :param obj_title: title of the target object

        :returns the target object or None if not found
        """
        url = urijoin(self.base_url, self.API_SAVED_OBJECTS_URL)
        found_obj = None

        for page_objs in self.fetch_objs(url):
            for obj in page_objs:
                if obj['type'] == obj_type and obj['attributes']['title'] == obj_title:
                    found_obj = obj
                    break

        if not found_obj:
            logging.warning("No %s found with title: %s", obj_type, obj_title)

        return found_obj

    def find_by_id(self, obj_type, obj_id):
        """Find an object by its type and title.

        :param obj_type: type of the target object
        :param obj_id: ID of the target object

        :returns the target object or None if not found
        """
        url = urijoin(self.base_url, self.API_SAVED_OBJECTS_URL)
        found_obj = None

        for page_objs in self.fetch_objs(url):
            for obj in page_objs:
                if obj['type'] == obj_type and obj['id'] == obj_id:
                    found_obj = obj
                    break

        if not found_obj:
            logging.warning("No %s found with title: %s", obj_type, obj_id)

        return found_obj

    def fetch_objs(self, url):
        """Find an object by its type and title.

        :param url: saved_objects endpoint

        :returns an iterator of the saved objects
        """
        fetched_objs = 0
        params = {
            'page':  1
        }

        while True:
            r_json = self.fetch(url, params=params)

            yield r_json['saved_objects']
            current_page = r_json['page']
            fetched_objs += len(r_json['saved_objects'])

            if fetched_objs >= r_json['total']:
                break

            params['page'] = current_page + 1

    def get_object(self, obj_type, obj_id):
        """Get the object by its type and id.

        :param obj_type: type of the target object
        :param obj_id: ID of the target object

        :returns the target object
        """
        url = urijoin(self.base_url, self.API_SAVED_OBJECTS_URL, obj_type, obj_id)

        r = None
        try:
            r = self.fetch(url)
        except requests.exceptions.HTTPError as error:
            if error.response.status_code == 404:
                logging.warning("No %s found with id: %s", obj_type, obj_id)
            else:
                raise error

        return r

    def delete_object(self, obj_type, obj_id):
        """Delete the object with a given type and id.

        :param obj_type: type of the target object
        :param obj_id: ID of the target object

        """
        url = urijoin(self.base_url, self.API_SAVED_OBJECTS_URL, obj_type, obj_id)
        try:
            self.delete(url)
        except requests.exceptions.HTTPError as error:
            if error.response.status_code == 404:
                logging.warning("No %s found with id: %s", obj_type, obj_id)
            else:
                raise error

    def update_object(self, obj_type, obj_id, attr, value):
        """Update an attribute of a target object of a given type and id.

        :param obj_type: type of the target object
        :param obj_id: ID of the target object
        :param attr: attribute to update
        :param value: new value of attribute
        """
        url = urijoin(self.base_url, self.API_SAVED_OBJECTS_URL, obj_type, obj_id)
        params = {
            "attributes": {
                attr: value
            }
        }
        r = None

        try:
            r = self.put(url, data=params)
        except requests.exceptions.HTTPError as error:
            if error.response.status_code == 404:
                logging.warning("No %s found with id: %s", obj_type, obj_id)
            elif error.response.status_code == 400:
                logging.warning("Impossible to update attribute %s with value %s, for %s with id %s",
                                attr, value, obj_type, obj_id)
            else:
                raise error

        return r


class Dashboard(KibanaClient):

    API_DASHBOARDS_URL = 'api/kibana/dashboards'
    API_IMPORT_COMMAND = 'import'
    API_EXPORT_COMMAND = 'export'

    def __init__(self, base_url):
        self.base_url = base_url
        self.saved_objects = SavedObjects(self.base_url)

    def export_dashboard_by_title(self, dashboard_title):
        """Export a dashboard identified by its title.

        :param dashboard_title: title of the dashboard

        :returns the dashboard exported
        """
        dashboard = self.saved_objects.find_by_title("dashboard", dashboard_title)

        if not dashboard:
            logging.error("Impossible to export dashboard with title %s, not found", dashboard_title)
            return

        dashboard_id = dashboard['id']
        dashboard = self.export_dashboard_by_id(dashboard_id)

        return dashboard

    def export_dashboard_by_id(self, dashboard_id):
        """Export a dashboard identified by its ID.

        :param dashboard_id: ID of the dashboard

        :returns the dashboard exported
        """
        url = urijoin(self.base_url, self.API_DASHBOARDS_URL, self.API_EXPORT_COMMAND + '?dashboard=' + dashboard_id)

        dashboard = None
        try:
            dashboard = self.fetch(url)

            if 'error' in dashboard['objects'][0]:
                msg = dashboard['objects'][0]['error']['message'].lower()
                logging.error("Impossible to export dashboard with id %s, %s", dashboard_id, msg)
                dashboard = None
        except requests.exceptions.HTTPError as error:
            if error.response.status_code == 400:
                logging.error("Impossible to export dashboard with id %s", dashboard_id)
            else:
                raise error

        return dashboard

    def import_objects_from_file(self, file_name, exclude_dash=False, exclude_ip=False,
                                 exclude_vis=False, exclude_src=False, force=False):
        """Import objects from a file in Sigil repository.

        :param file_name: name of the target file
        :param exclude_dash: do not import dashboards
        :param exclude_ip: do not import index patterns
        :param exclude_vis: do not import visualizations
        :param exclude_src: do not import searches
        :param force: overwrite any existing objects on ID conflict

        :returns the list of imported objects, with errors (in case something went wrong)
        """
        objects = self.extract_objects_from_file(file_name)

        if not objects:
            return

        result = self.import_objects(objects, exclude_dash, exclude_ip, exclude_vis, exclude_src, force)
        return result

    def import_objects(self, data, exclude_dash=False, exclude_ip=False,
                       exclude_vis=False, exclude_src=False, force=False):
        """Import objects from a dictionary.

        :param data: dictionary
        :param exclude_dash: do not import dashboards
        :param exclude_ip: do not import index patterns
        :param exclude_vis: do not import visualizations
        :param exclude_src: do not import searches
        :param force: overwrite any existing objects on ID conflict

        :returns the list of imported objects, with errors (in case something went wrong)
        """
        url = urijoin(self.base_url, self.API_DASHBOARDS_URL, self.API_IMPORT_COMMAND)
        params = {
            'exclude': [],
            'force': 'false'
        }

        if exclude_dash:
            params['exclude'].append(DASHBOARD)
        if exclude_ip:
            params['exclude'].append(INDEX_PATTERN)
        if exclude_vis:
            params['exclude'].append(VISUALIZATION)
        if exclude_src:
            params['exclude'].append(SEARCH)

        if force:
            params['force'] = 'true'

        response = self.post(url, data, params)

        total = len(response['objects'])
        for obj in response['objects']:
            if 'error' not in obj:
                continue

            response['objects'].remove(obj)
            logging.error("%s with id %s not imported, %s", obj['type'], obj['id'], obj['error']['message'])

        logging.info("%s/%s object(s) imported", len(response['objects']), total)
        return response

    @staticmethod
    def extract_objects_from_file(file_path, exclude_dash=False, exclude_ip=False, exclude_vis=False, exclude_src=False):
        """Extract objects from data in the Sigils repository and return its contents.

        :param file_path: dashboard file path
        :param exclude_dash: exclude dashboards
        :param exclude_ip: exclude index patterns
        :param exclude_vis: exclude visualizations
        :param exclude_src: exclude searches

        :returns: a dict with the list of extracted objects
        """
        json_content = Dashboard.__load_sigils_data(file_path)

        if not json_content:
            return None

        objects = []
        for entry in json_content.keys():
            if entry == "dashboard":

                if exclude_dash:
                    continue

                obj = {}
                obj['id'] = json_content[entry]['id']
                obj['type'] = DASHBOARD
                obj['attributes'] = json_content[entry]['value']
                objects.append(obj)
            else:
                for item in json_content[entry]:
                    if entry == "searches" and exclude_src:
                        continue
                    if entry == "visualizations" and exclude_vis:
                        continue
                    if entry == "index_patterns" and exclude_ip:
                        continue

                    obj = {}
                    obj['id'] = item['id']
                    obj['attributes'] = item['value']

                    if entry == "searches":
                        obj['type'] = SEARCH
                    elif entry == "visualizations":
                        obj['type'] = VISUALIZATION
                    elif entry == "index_patterns":
                        obj['type'] = INDEX_PATTERN

                    objects.append(obj)

        return {'objects': objects}

    @staticmethod
    def __load_sigils_data(file_path):
        """Load data from Sigils repository and return its contents.

        :param file_path: dashboard file path

        :returns: JSON of the dashboard, null if not found
        """
        sigils_bytes = pkgutil.get_data('panels', 'json' + '/' + file_path)
        sigils_str = sigils_bytes.decode(encoding='utf8')

        try:
            json_content = json.loads(sigils_str)
        except ValueError:
            json_content = None

        return json_content


def main():
    KIBITER_URL = "http://localhost:5601"

    example_dashboard = {
        "objects": [
            {
              "id": "80b956f0-b2cd-11e8-ad8e-85441f0c2e5c",
              "type": "visualization",
              "updated_at": "2018-09-07T18:40:33.247Z",
              "version": 1,
              "attributes": {
                "title": "Count Example",
                "visState": "{\"title\":\"Count Example\",\"type\":\"metric\",\"params\":{\"addTooltip\":true,\"addLegend\":false,\"type\":\"metric\",\"metric\":{\"percentageMode\":false,\"useRanges\":false,\"colorSchema\":\"Green to Red\",\"metricColorMode\":\"None\",\"colorsRange\":[{\"from\":0,\"to\":10000}],\"labels\":{\"show\":true},\"invertColors\":false,\"style\":{\"bgFill\":\"#000\",\"bgColor\":false,\"labelColor\":false,\"subText\":\"\",\"fontSize\":60}}},\"aggs\":[{\"id\":\"1\",\"enabled\":true,\"type\":\"count\",\"schema\":\"metric\",\"params\":{}}]}",
                "uiStateJSON": "{}",
                "description": "",
                "version": 1,
                "kibanaSavedObjectMeta": {
                  "searchSourceJSON": "{\"index\":\"90943e30-9a47-11e8-b64d-95841ca0b247\",\"query\":{\"query\":\"\",\"language\":\"lucene\"},\"filter\":[]}"
                }
              }
            },
            {
              "id": "90943e30-9a47-11e8-b64d-95841ca0b247",
              "type": "index-pattern",
              "updated_at": "2018-09-07T18:39:47.683Z",
              "version": 1,
              "attributes": {
                "title": "kibana_sample_data_logs",
                "timeFieldName": "timestamp",
                "fields": "<truncated for example>",
                "fieldFormatMap": "{\"hour_of_day\":{}}"
              }
            },
            {
              "id": "942dcef0-b2cd-11e8-ad8e-85441f0c2e5c",
              "type": "dashboard",
              "updated_at": "2018-09-07T18:41:05.887Z",
              "version": 1,
              "attributes": {
                "title": "Example Dashboard",
                "hits": 0,
                "description": "",
                "panelsJSON": "[{\"gridData\":{\"w\":24,\"h\":15,\"x\":0,\"y\":0,\"i\":\"1\"},\"version\":\"7.0.0-alpha1\",\"panelIndex\":\"1\",\"type\":\"visualization\",\"id\":\"80b956f0-b2cd-11e8-ad8e-85441f0c2e5c\",\"embeddableConfig\":{}}]",
                "optionsJSON": "{\"darkTheme\":false,\"useMargins\":true,\"hidePanelTitles\":false}",
                "version": 1,
                "timeRestore": False,
                "kibanaSavedObjectMeta": {
                  "searchSourceJSON": "{\"query\":{\"query\":\"\",\"language\":\"lucene\"},\"filter\":[]}"
                }
              }
            }
        ]
    }

    dash = Dashboard(KIBITER_URL)
    dash.import_objects(example_dashboard)

    # Test SavedObjects
    found = dash.saved_objects.find_by_title("visualization", "Count Example")
    not_found = dash.saved_objects.find_by_title("visualization", "Example")
    found = dash.saved_objects.find_by_id("visualization", "80b956f0-b2cd-11e8-ad8e-85441f0c2e5c")
    found = dash.saved_objects.get_object("visualization", "80b956f0-b2cd-11e8-ad8e-85441f0c2e5c")
    not_found = dash.saved_objects.get_object("visualization", "80b956f0-b2cd-11e8-ad8e-85441f0c2e5e")
    result = dash.saved_objects.update_object("dashboard", "942dcef0-b2cd-11e8-ad8e-85441f0c2e5c", "title", "XYZ")
    not_found = dash.saved_objects.update_object("dashboard", "942dcef0-b2cd-11e8-ad8e-85441f0c2e5x", "title", "XYZ")
    wrong_attributes = dash.saved_objects.update_object("dashboard", "942dcef0-b2cd-11e8-ad8e-85441f0c2e5c", "title", {"x": "y"})
    found = dash.saved_objects.find_by_title("dashboard", "XYZ")
    result = dash.saved_objects.update_object("dashboard", "942dcef0-b2cd-11e8-ad8e-85441f0c2e5c", "title", "Example Dashboard")
    found = dash.saved_objects.find_by_title("dashboard", "Example Dashboard")

    # version is not updated in the .kibana, but it is in the object returned by the API
    # the updated_at value changes at any time there is a modification in the object, and it is reflected in the .kibana
    result = dash.saved_objects.update_object("dashboard", "942dcef0-b2cd-11e8-ad8e-85441f0c2e5c", "title", "ABC")
    found = dash.saved_objects.find_by_title("dashboard", "ABC")
    result = dash.saved_objects.update_object("dashboard", "942dcef0-b2cd-11e8-ad8e-85441f0c2e5c", "title", "DEF")
    found = dash.saved_objects.find_by_title("dashboard", "DEF")
    result = dash.saved_objects.update_object("dashboard", "942dcef0-b2cd-11e8-ad8e-85441f0c2e5c", "title", "GHI")
    found = dash.saved_objects.find_by_title("dashboard", "GHI")
    result = dash.saved_objects.update_object("dashboard", "942dcef0-b2cd-11e8-ad8e-85441f0c2e5c", "title", "LMN")
    found = dash.saved_objects.find_by_title("dashboard", "LMN")
    # check update_at is refreshed when forcing the import of an existing object
    previous_date = found['updated_at']
    objects = dash.import_objects({'objects': [found]}, force=True)
    current_date = objects['objects'][0]['updated_at']

    result = dash.saved_objects.delete_object("visualization", "80b956f0-b2cd-11e8-ad8e-85441f0c2e5c")
    found = dash.saved_objects.find_by_id("dashboard", "942dcef0-b2cd-11e8-ad8e-85441f0c2e5c")
    panels = found['attributes']['panelsJSON']
    result = dash.saved_objects.update_object("dashboard", "942dcef0-b2cd-11e8-ad8e-85441f0c2e5c", "panelsJSON", '[]')
    found = dash.saved_objects.find_by_id("dashboard", "942dcef0-b2cd-11e8-ad8e-85441f0c2e5c")
    # deletions cause problems when exporting the dashboard, if the deleted visualization is not removed from the dashboard
    # result = dash.saved_objects.update_object("dashboard", "942dcef0-b2cd-11e8-ad8e-85441f0c2e5c", "panelsJSON", panels)
    # found = dash.saved_objects.find_by_id("dashboard", "942dcef0-b2cd-11e8-ad8e-85441f0c2e5c")

    # Test Dashboard
    result = dash.export_dashboard_by_id("942dcef0-b2cd-11e8-ad8e-85441f0c2e5c")
    not_found = dash.export_dashboard_by_id("942dcef0-b2cd-11e8-ad8e-85441f0c2e5x")
    result = dash.export_dashboard_by_title(found['attributes']['title'])
    result = dash.saved_objects.delete_object("dashboard", "942dcef0-b2cd-11e8-ad8e-85441f0c2e5c")
    result = dash.saved_objects.delete_object("visualization", "80b956f0-b2cd-11e8-ad8e-85441f0c2e5c")
    result = dash.saved_objects.delete_object("index-pattern", "90943e30-9a47-11e8-b64d-95841ca0b247")

    # Test import from Sigils
    # error in importing Gerrit dashboard, release date not allowed (mapping set to strict)
    result = dash.import_objects_from_file("gerrit.json", force=True, exclude_src=True)
    found = dash.saved_objects.find_by_title("visualization", "gerrit_patchsets_per_changeset")
    # since Gerrit dashboard has not been imported, the object is not found
    not_found = dash.saved_objects.find_by_title("dashboard", "Gerrit")

    objects = dash.extract_objects_from_file("gerrit.json")
    for obj in objects['objects']:
        dash.saved_objects.delete_object(obj['type'], obj['id'])

    dashboard = objects['objects'][0]
    # setting the updated_at and version values doesn't have any effect
    dashboard['updated_at'] = dashboard['attributes']['release_date']
    dashboard['version'] = 100
    dashboard['attributes'].pop('release_date')
    
    # the index pattern is needed to visualize the data
    index_pattern = dash.extract_objects_from_file("gerrit-index-pattern.json")
    index_pattern['objects'][0]['attributes'].pop('release_date')
    objects['objects'].append(index_pattern['objects'][0])

    result = dash.import_objects(objects, force=True)
    result = dash.export_dashboard_by_title("Gerrit")


if __name__ == "__main__":
    main()
