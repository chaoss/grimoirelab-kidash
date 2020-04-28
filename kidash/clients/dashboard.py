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

import logging
import requests


from kidash.clients.http import HttpClient
from kidash.utils import urijoin

DASHBOARD = "dashboard"
INDEX_PATTERN = "index-pattern"
SEARCH = "search"
VISUALIZATION = "visualization"

logger = logging.getLogger(__name__)


class Dashboard(HttpClient):
    """Dashboard API client.

    This class allows to perform operations against the Dashboard API, such
    as exporting and importing dashboard.

    :param base_url: the Kibana URL
    """
    API_DASHBOARDS_URL = 'api/kibana/dashboards'
    API_IMPORT_COMMAND = 'import'
    API_EXPORT_COMMAND = 'export'

    def __init__(self, base_url):
        super().__init__(base_url)

    def export_dashboard(self, dashboard_id):
        """Export a dashboard identified by its ID.

        This method returns a dashboard based on `dashboard_id` using the endpoint
        `export` of the Dashboard API.

        :param dashboard_id: ID of the dashboard

        :returns the dashboard exported
        """
        url = urijoin(self.base_url, self.API_DASHBOARDS_URL, self.API_EXPORT_COMMAND + '?dashboard=' + dashboard_id)

        try:
            dashboard = self.fetch(url)

            errors = [obj for obj in dashboard['objects'] if 'error' in obj]
            if errors:
                msg = errors[0]
                cause = "Impossible to export dashboard with id %s, %s" % (dashboard_id, msg)
                logger.error(cause)
                dashboard = None
        except requests.exceptions.HTTPError as error:
            logger.error(error)
            dashboard = None

        return dashboard

    def import_objects(self, objects, exclude_dashboards=False, exclude_index_patterns=False,
                       exclude_visualizations=False, exclude_searches=False, force=False):
        """Import objects from a dictionary to Kibana.

        This method import a list of objects to the Kibana instance using the
        endpoint `import` of the Dashboard API.

        :param objects: list of objects
        :param exclude_dashboards: do not import dashboards
        :param exclude_index_patterns: do not import index patterns
        :param exclude_visualizations: do not import visualizations
        :param exclude_searches: do not import searchesDataExportError
        :param force: overwrite any existing objects on ID conflict
        """
        url = urijoin(self.base_url, self.API_DASHBOARDS_URL, self.API_IMPORT_COMMAND)
        params = {
            'exclude': [],
            'force': 'false'
        }

        if exclude_dashboards:
            params['exclude'].append(DASHBOARD)
        if exclude_index_patterns:
            params['exclude'].append(INDEX_PATTERN)
        if exclude_visualizations:
            params['exclude'].append(VISUALIZATION)
        if exclude_searches:
            params['exclude'].append(SEARCH)

        if force:
            params['force'] = 'true'

        response = self.post(url, objects, params)

        total = len(response['objects'])
        for obj in response['objects']:
            if 'error' not in obj:
                continue

            response['objects'].remove(obj)
            logger.error("%s with id %s not imported, %s", obj['type'], obj['id'], obj['error']['message'].lower())

        logger.info("%s/%s object(s) imported", len(response['objects']), total)
