#!/usr/bin/python3
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
#   Alvaro del Castillo San Felix <acs@bitergia.com>
#

import copy
import json
import logging

import os
import os.path

import requests
import urllib3

from kidash.clients.saved_objects import SavedObjects
from kidash.clients.dashboard import Dashboard

logger = logging.getLogger(__name__)

ES_VER = None
ES6_HEADER = {"Content-Type": "application/json", "kbn-xsrf": "true"}
RELEASE_VERSION = 'version'
STUDY_PATTERN = "_study_"

VISUALIZATION = "visualization"
INDEX_PATTERN = "index_pattern"
SEARCH = "search"

DASHBOARD = "dashboard"
VISUALIZATIONS = "visualizations"
INDEX_PATTERNS = "index_patterns"
SEARCHES = "searches"


def find_item_json(kibana_url, type_, item_id):
    """ Find and item (dashboard, vis, search, index pattern) using its id """

    item_json = {}
    saved_objs = SavedObjects(kibana_url)
    obj = saved_objs.get_object(type_, item_id)
    if obj:
        item_json = obj

    return item_json


def clean_dashboard(dash_json, data_sources=None, add_vis_studies=False, viz_titles=None):
    """ Remove all items that are not from the data sources or that are studies"""

    if data_sources:
        logger.debug("Cleaning dashboard for %s", data_sources)
    if not add_vis_studies:
        logger.debug("Cleaning dashboard from studies vis")

    dash_json_clean = copy.deepcopy(dash_json)

    dash_json_clean['panelsJSON'] = ""

    # Time to add the panels (widgets) related to the data_sources
    panelsJSON = json.loads(dash_json['panelsJSON'])
    clean_panelsJSON = []
    for panel in panelsJSON:
        if STUDY_PATTERN in panel['id'] and not add_vis_studies:
            continue
        if data_sources:
            for ds in data_sources:

                if panel['id'].split("_")[0] == ds or\
                   panel['title'].split()[0].lower() == ds or\
                   viz_titles[panel['id']].split("_")[0] == ds:
                    clean_panelsJSON.append(panel)
                    break
        else:
            clean_panelsJSON.append(panel)
    dash_json_clean['panelsJSON'] = json.dumps(clean_panelsJSON)

    return dash_json_clean


def fix_dashboard_heights(item_json):
    """ In vis of height 1 increase it to 2

    This method is designed to help in the migration from dashboards
    created with Kibana < 6, in which with height 1 the visualization could
    be shown completly in some cases, to Kibana > 6, in which with a height of
    1 the title bar of the visualization makes imposible to show a complete
    visualization of any kind.

    """

    panels = json.loads(item_json["panelsJSON"])

    for panel in panels:
        if 'size_y' not in panel:
            # The layout definition is not from Kibana < 6
            # In Kibana >= 6 the height is the "h" field in:
            # "gridData": {"x": 0,"y": 0,"w": 4,"h": 2,"i": "1"}
            logger.debug("Not fixing height in Kibana >= 6 versions.")
            break

        if panel['size_y'] == 1:
            panel['size_y'] += 1

    item_json["panelsJSON"] = json.dumps(panels)

    return item_json


def fix_dash_bool_filters(dash_json):
    """ The bool filter is pretty deep inside the JSON document """
    if "kibanaSavedObjectMeta" in dash_json and "searchSourceJSON" in dash_json["kibanaSavedObjectMeta"]:
        meta_saved =  json.loads(dash_json["kibanaSavedObjectMeta"]["searchSourceJSON"])
        if 'filter' in meta_saved:
            for filter_ in meta_saved['filter']:
                query = filter_.get('query')
                if query and 'match' in query:
                    match = filter_['query']['match']
                    for field in match:
                        if match[field]['type'] == 'phrase':
                            if match[field]['query'] == 1:
                                match[field]['query'] = True
                            elif match[field]['query'] == 0:
                                match[field]['query'] = False
        dash_json["kibanaSavedObjectMeta"]["searchSourceJSON"] = json.dumps(meta_saved)

    return dash_json


def add_vis_style(item_json):
    """ Right now a fix style is added using the correct font size """

    if "visState" in item_json:
        state = json.loads(item_json["visState"])
        if state["type"] != "metric":
            return item_json
        if "fontSize" in state["params"]:
            # In Kibana6 the params for a metric include several new params
            if "metric" in state['params']:
                # A kibana6 vis, don't modify it
                return item_json
            state['params']["metric"] = {
                "percentageMode": False,
                "useRanges": False,
                "colorSchema": "Green to Red",
                "metricColorMode": "None",
                "colorsRange": [
                    {
                        "from": 0,
                        "to": 10000
                    }
                ],
                "labels": {
                    "show": True
                },
                "invertColors": False,
                "style": {
                    "bgFill": "#000",
                    "bgColor": False,
                    "labelColor": False,
                    "subText": "",
                    "fontSize": state['params']['fontSize']
                }
            }
            item_json['visState'] = json.dumps(state)
    return item_json


def import_item_json(kibana_url, type_, item_id, item_json, data_sources=None,
                     add_vis_studies=False, viz_titles=None):
    """ Import an item in Elasticsearch  """
    if not add_vis_studies:
        if type_ == 'dashboard':
            # Clean ths vis related to studies
            item_json = clean_dashboard(item_json, data_sources=None,
                                        add_vis_studies=add_vis_studies)
    if data_sources:
        if type_ == 'dashboard':
            item_json = clean_dashboard(item_json, data_sources, add_vis_studies, viz_titles)
        if type_ == 'search':
            if not is_search_from_data_sources(item_json, data_sources):
                logger.debug("Search %s not for %s. Not included.",
                             item_id, data_sources)
                return
        elif type_ == 'index_pattern':
            if not is_index_pattern_from_data_sources(item_json, data_sources):
                logger.debug("Index pattern %s not for %s. Not included.",
                             item_id, data_sources)
                return
        elif type_ == 'visualization':
            if not is_vis_from_data_sources(item_json, data_sources):
                logger.debug("Vis %s not for %s. Not included.",
                             item_id, data_sources)
                return

    if type_ == 'dashboard':
        # Bool filters value must be true/false no 1/0 in es6
        item_json = fix_dash_bool_filters(item_json)
        # Vis height of 1 is too small for kibana6
        item_json = fix_dashboard_heights(item_json)

    if type_ == 'visualization':
        # Metric vis includes in es6 new params for the style
        item_json = add_vis_style(item_json)

    item_json.pop('release_date', None)

    saved_objects = SavedObjects(kibana_url)

    obj = saved_objects.get_object(type_, item_id)
    if obj:
        saved_objects.update_object(type_, item_id, item_json)
    else:
        saved_objects.create_object(type_, item_json, obj_id=item_id)

    return item_json


def get_index_pattern_json(kibana_url, index_pattern_id):
    index_pattern_json = find_item_json(kibana_url, "index-pattern",
                                        index_pattern_id)

    return index_pattern_json


def get_index_pattern_from_meta(meta_data):
    index = None
    mdata = meta_data["searchSourceJSON"]
    mdata = json.loads(mdata)
    if "index" in mdata:
        index = mdata["index"]
    if "filter" in mdata:
        if len(mdata["filter"]) > 0:
            index = mdata["filter"][0]["meta"]["index"]
    return index


def read_panel_file(panel_file):
    """Read a panel file (in JSON format) and return its contents.

    :param panel_file: name of JSON file with the dashboard to read
    :returns: dictionary with dashboard read,
                None if not found or wrong format
    """

    try:
        logger.debug("Reading panel from directory: %s", panel_file)
        with open(panel_file, 'r') as f:
            kibana_str = f.read()
    except FileNotFoundError:
        logger.error("Panel not found (not in directory, "
                     + "no panels module): %s",
                     panel_file)
        return None

    try:
        kibana_dict = json.loads(kibana_str)
    except ValueError:
        logger.error("Wrong file format (not JSON): %s", panel_file)
        return None
    return kibana_dict


def get_dashboard_name(panel_file):
    """ Return the dashboard name included in a JSON panel file """

    dash_name = None

    kibana = read_panel_file(panel_file)
    if kibana and 'dashboard' in kibana:
        dash_name = kibana['dashboard']['id']
    elif kibana:
        logger.error("Wrong panel format (can't find 'dashboard' or 'index_patterns' fields): %s",
                     panel_file)
    return dash_name


def get_index_patterns_name(panel_file):
    """
    Return  in a file

    :param panel_file: file with the index patterns definition
    :return: a list with the name of the index patterns
    """

    index_patterns_name = []

    kibana = read_panel_file(panel_file)
    if kibana and 'index_patterns' in kibana:
        for index_pattern in kibana['index_patterns']:
            index_patterns_name.append(index_pattern['id'])
    elif kibana:
        logger.error("Wrong panel format (can't find 'index_patterns' fields): %s",
                     panel_file)
    return index_patterns_name


def is_search_from_data_sources(search, data_sources):
    found = False
    index_pattern = \
        get_index_pattern_from_meta(search['kibanaSavedObjectMeta'])

    for data_source in data_sources:
        # ex: github_issues
        if data_source == index_pattern.split("_")[0]:
            found = True
            break

    return found


def is_vis_from_data_sources(vis, data_sources):
    found = False
    vis_title = vis['value']['title']

    for data_source in data_sources:
        # ex: github_issues_evolutionary
        if data_source == vis_title.split("_")[0]:
            found = True
            break

    return found


def is_vis_study(vis):
    vis_study = False

    if STUDY_PATTERN in vis['id']:
        vis_study = True

    return vis_study


def is_index_pattern_from_data_sources(index, data_sources):
    found = False
    es_index = index['value']['title']

    for data_source in data_sources:
        # ex: github_issues
        if data_source == es_index.split("_")[0]:
            found = True
            break

    return found


def import_dashboard(kibana_url, import_file, data_sources=None, add_vis_studies=False, strict=False):
    """ Import a dashboard from a file
    """

    logger.debug("Reading panels JSON file: %s", import_file)
    json_to_import = read_panel_file(import_file)

    if json_to_import is None:
        logger.error("Can not find a valid JSON in: %s", import_file)
        raise RuntimeError("Can not find a valid JSON in: %s" % import_file)

    if 'dashboard' not in json_to_import and 'index_patterns' not in json_to_import:
        logger.error("Wrong file format (can't find dashboard or index_patterns fields): %s",
                     import_file)
        raise RuntimeError("Wrong file format (can't find dashboard or index_patterns fields): %s" %
                           import_file)

    if 'dashboard' in json_to_import:
        logger.debug("Panel detected.")

        dash_id = json_to_import['dashboard'].get('id')

        if not dash_id:
            raise ValueError("'id' field not found in ", + import_file)

        import_json = True
        strict = True
        if strict:
            logger.debug("Retrieving dashboard %s to check release date.", dash_id)
            current_panel = fetch_dashboard(kibana_url, dash_id)
            if current_panel['dashboard']:
                import_json = new_release(current_panel['dashboard'], json_to_import['dashboard'])

        if import_json:
            feed_dashboard(json_to_import, kibana_url, data_sources, add_vis_studies)
            logger.info("Dashboard %s imported", get_dashboard_name(import_file))
        else:
            logger.warning("Dashboard %s not imported from %s. Newer or equal version found in Kibana.",
                           dash_id, import_file)

    elif 'index_patterns' in json_to_import:
        logger.debug("Index-Pattern detected.")

        for index_pattern in json_to_import['index_patterns']:
            ip_id = index_pattern.get('id')

            if not ip_id:
                raise ValueError("'id' field not found in ", + import_file)

            import_json = True
            strict = True
            if strict:
                logger.debug("Retrieving index pattern %s to check release date.", ip_id)
                current_ip = fetch_index_pattern(kibana_url, ip_id)
                import_json = new_release(current_ip, index_pattern)

            if import_json:
                feed_dashboard({"index_patterns": [index_pattern]}, kibana_url, data_sources, add_vis_studies)
                logger.info("Index pattern %s from %s imported", ip_id, get_index_patterns_name(import_file))

            else:
                logger.warning("Index Pattern %s not imported from %s. Newer or equal version found in Kibana.",
                                ip_id, import_file)

    else:
        logger.warning("Strict mode supported only for panels and index patterns.")


def new_release(current_item, item_to_import):
    """Check whether a release is newer than another one

    :param current_item:
    :param item_to_import:
    :return: True if import release is newer than current one
    """

    current_release = current_item['value'].get(RELEASE_VERSION)
    import_release = item_to_import['value'].get(RELEASE_VERSION)
    logger.debug("Current item release version %s vs item to import version %s", current_release, import_release)
    is_new = True
    if current_release and import_release and current_release >= import_release:
        is_new = False

    return is_new


# def create_kibana_index(kibana_url):
#     """
#     Force the creation of the kibana index using the kibana API
#     :param kibana_url: Kibana URL
#     :return:
#     """
#
#     def set_kibana_setting(endpoint_url, data_value):
#         set_ok = False
#
#         try:
#             res = requests_ses.post(endpoint_url, headers=ES6_HEADER,
#                                     data=json.dumps(data_value), verify=False)
#             res.raise_for_status()
#             # With Search guard if the auth is invalid the URL is redirected to the login
#             # We need to detect that and record it as an error
#             if res.history and res.history[0].is_redirect:
#                 logging.error("Problems with search guard authentication %s" % endpoint_url)
#             else:
#                 set_ok = True
#         except requests.exceptions.HTTPError:
#             logging.error("Impossible to set %s: %s", endpoint_url, str(res.json()))
#
#         return set_ok
#
#     kibana_settings_url = kibana_url + '/api/kibana/settings'
#
#     # Configure the default index with the default value in Kibana
#     # If the kibana index does not exists, it is created by Kibana
#     endpoint = 'defaultIndex'
#     data_value = {"value": None}
#     endpoint_url = kibana_settings_url + '/' + endpoint
#
#     return set_kibana_setting(endpoint_url, data_value)


def configure_settings(kibana_url, settings):
    """Configure the Kibana config"""

    saved_objs = SavedObjects(kibana_url)
    saved_objs.create_object("config", settings)

# def check_kibana_index(es_url, kibana_url, kibana_index=".kibana"):
#     """
#     Check if kibana index already exists and if not, create it
#
#     :param es_url: Elasticsearch URL with kibana
#     :param kibana_url: Kibana URL
#     :param kibana_index: index with kibana information
#     :return:
#     """
#     kibana_index_ok = False
#     kibana_index_url = es_url + "/" + kibana_index
#
#     try:
#         res = requests_ses.get(kibana_index_url, verify=False)
#         res.raise_for_status()
#         kibana_index_ok = True
#     except:
#         logging.info("%s does not exist. Creating it." % kibana_index_url)
#         if create_kibana_index(kibana_url):
#             kibana_index_ok = True
#
#     return kibana_index_ok


def feed_dashboard(dashboard, kibana_url, data_sources=None,
                   add_vis_studies=False):
    """ Import a dashboard. If data_sources are defined, just include items
        for this data source.
    """

    if 'dashboard' in dashboard:
        # Get viz titles because the are needed to check what items must be
        # excluded by data source name in case that option is enabled
        viz_titles = {}
        if 'visualizations' in dashboard:
            for visualization in dashboard['visualizations']:
                viz_id = visualization['id']
                viz_title = visualization['value']['title']
                viz_titles[viz_id] = viz_title

        import_item_json(kibana_url, "dashboard", dashboard['dashboard']['id'],
                         dashboard['dashboard']['value'], data_sources, add_vis_studies,
                         viz_titles=viz_titles)

    if 'searches' in dashboard:
        for search in dashboard['searches']:
            import_item_json(kibana_url, "search", search['id'], search['value'],
                             data_sources)

    if 'index_patterns' in dashboard:
        for index in dashboard['index_patterns']:
            if not data_sources or \
                    is_index_pattern_from_data_sources(index, data_sources):
                import_item_json(kibana_url, "index-pattern",
                                 index['id'], index['value'])
            else:
                logger.debug("Index pattern %s not for %s. Not included.",
                             index['id'], data_sources)

    if 'visualizations' in dashboard:
        for vis in dashboard['visualizations']:
            if not add_vis_studies and is_vis_study(vis):
                logger.debug("Vis %s is for an study. Not included.", vis['id'])
            elif not data_sources or is_vis_from_data_sources(vis, data_sources):
                import_item_json(kibana_url, "visualization",
                                 vis['id'], vis['value'])
            else:
                logger.debug("Vis %s not for %s. Not included.",
                             vis['id'], data_sources)


def fetch_index_pattern(kibana_url, ip_id):
    """
    Fetch an index pattern JSON definition from Kibana and return it.

    :param kibana_url: Kibana URL
    :param ip_id: index pattern identifier
    :return: a dict with index pattern data
    """
    logger.debug("Fetching index pattern %s", ip_id)
    ip_json = get_index_pattern_json(kibana_url, ip_id)

    index_pattern = {"id": ip_id,
                     "value": ip_json}

    return index_pattern


def fetch_dashboard(kibana_url, dash_id):
    """
    Fetch a dashboard JSON definition from Kibana and return it.

    :param kibana_url: Kibana URL
    :param dash_id: dashboard identifier
    :return: a dict with the dashboard data (vis, searches and index patterns)
    """

    dashboard = Dashboard(kibana_url)
    objects = dashboard.export_dashboard(dash_id)

    kibana = {
        DASHBOARD: None,
        VISUALIZATIONS: [],
        INDEX_PATTERNS: [],
        SEARCHES: []
    }

    if not objects:
        return kibana

    for obj in objects.get('objects', []):
        obj_id = obj['id']
        obj_type = obj['type']

        if obj_type == DASHBOARD:
            kibana[DASHBOARD] = {'id:': obj_id, 'value': obj}
        elif obj_type == VISUALIZATION:
            kibana[VISUALIZATIONS].append({'id:': obj_id, 'value': obj})
        elif obj_type == SEARCHES:
            kibana[SEARCHES].append({'id:': obj_id, 'value': obj})
        elif obj_type == INDEX_PATTERN:
            kibana[INDEX_PATTERNS].append({'id:': obj_id, 'value': obj})
        else:
            logging.info("object %s with type %s ignored.", obj_id, obj_type)

    return kibana


def export_dashboard_files(dash_json, export_file, split_index_patterns=False):

    if os.path.isfile(export_file):
        logging.info("%s exists. Remove it before running.", export_file)
        raise RuntimeError("%s exists. Remove it before running." % export_file)

    with open(export_file, 'w') as f:
        if not split_index_patterns:
            f.write(json.dumps(dash_json, indent=4, sort_keys=True))
        else:
            index_patterns = dash_json.pop("index_patterns")

            with open(export_file, 'w') as f:
                f.write(json.dumps(dash_json, indent=4, sort_keys=True))

            export_folder = os.path.dirname(export_file)

            for index_pattern in index_patterns:

                export_file_index = os.path.join(export_folder, index_pattern['id'] + "-index-pattern.json")
                if os.path.isfile(export_file_index):
                    logging.info("%s exists. Remove it before running.", export_file_index)
                    raise RuntimeError("%s exists. Remove it before running." % export_file_index)

                index_pattern_importable = {"index_patterns": [index_pattern]}
                with open(export_file_index, 'w') as f:
                    f.write(json.dumps(index_pattern_importable, indent=4, sort_keys=True))


def export_dashboard(kibana_url, dash_id, export_file, split_index_patterns=False):
    """
    Export a dashboard from Kibana to a file in JSON format. If split_index_patterns is defined it will
    store the index patterns in separate files.

    :param kibana_url: Kibana URL
    :param dash_id: dashboard identifier
    :param export_file: name of the file in which to export the dashboard
    :param split_index_patterns: store the index patterns in separate files
    """

    logger.debug("Exporting dashboard %s to %s", dash_id, export_file)

    kibana = fetch_dashboard(kibana_url, dash_id)
    export_dashboard_files(kibana, export_file, split_index_patterns)

    logger.debug("Done")
