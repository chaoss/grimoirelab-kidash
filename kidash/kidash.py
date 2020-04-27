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

import dateutil
import os.path

from datetime import datetime as dt

import requests
import urllib3


logger = logging.getLogger(__name__)

ES_VER = None
ES6_HEADER = {"Content-Type": "application/json", "kbn-xsrf": "true"}
HEADERS_JSON = {"Content-Type": "application/json"}
RELEASE_DATE = 'release_date'
STUDY_PATTERN = "_study_"

BACKOFF_FACTOR = 0.2
MAX_RETRIES = 21
MAX_RETRIES_ON_REDIRECT = 5
MAX_RETRIES_ON_READ = 8
MAX_RETRIES_ON_CONNECT = 21
STATUS_FORCE_LIST = [408, 409, 429, 502, 503, 504]


def grimoire_con(insecure=True, conn_retries=MAX_RETRIES_ON_CONNECT, total=MAX_RETRIES):
    conn = requests.Session()
    retries = urllib3.util.Retry(total=total, connect=conn_retries, read=MAX_RETRIES_ON_READ,
                                 redirect=MAX_RETRIES_ON_REDIRECT, backoff_factor=BACKOFF_FACTOR,
                                 method_whitelist=False, status_forcelist=STATUS_FORCE_LIST)
    adapter = requests.adapters.HTTPAdapter(max_retries=retries)
    conn.mount('http://', adapter)
    conn.mount('https://', adapter)

    if insecure:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        conn.verify = False

    return conn


requests_ses = grimoire_con()


class ElasticSearch:

    def __init__(self, url, index):

        self.url = url
        self.index = index

        self.index_url = self.url + "/" + self.index

        self.requests = grimoire_con(True)

        res = self.requests.get(self.index_url)

        headers = {"Content-Type": "application/json"}
        if res.status_code != 200:
            # Index does no exists
            r = self.requests.put(self.index_url, headers=headers)
            if r.status_code != 200:
                logger.error("Can't create index {} ({})".format(
                             self.index, r.status_code))
                raise Exception
            else:
                logger.info("Created index {}".format(self.index))


def find_elasticsearch_version(elastic):
    global ES_VER
    if not ES_VER:
        res = requests_ses.get(elastic.url)
        main_ver = res.json()['version']['number'].split(".")[0]
        ES_VER = int(main_ver)
    return ES_VER


def find_item_json(elastic, type_, item_id):
    """ Find and item (dashboard, vis, search, index pattern) using its id """
    elastic_ver = find_elasticsearch_version(elastic)

    if elastic_ver < 6:
        item_json_url = elastic.index_url + "/" + type_ + "/" + item_id
    else:
        if not item_id.startswith(type_ + ":"):
            # Inside a dashboard ids don't include type_:
            item_id = type_ + ":" + item_id
        # The type_is included in the item_id
        item_json_url = elastic.index_url + "/doc/" + item_id

    res = requests_ses.get(item_json_url, verify=False)
    if res.status_code == 200 and res.status_code == 404:
        res.raise_for_status()

    item_json = res.json()

    if "_source" not in item_json:
        logger.debug("Can not find type %s item %s", type_, item_id)
        item_json = {}
    else:
        if elastic_ver < 6:
            item_json = item_json["_source"]
        else:
            item_json = item_json["_source"][type_]

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


def import_item_json(elastic, type_, item_id, item_json, data_sources=None,
                     add_vis_studies=False, viz_titles=None):
    """ Import an item in Elasticsearch  """
    elastic_ver = find_elasticsearch_version(elastic)

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

    if elastic_ver < 6:
        item_json_url = elastic.index_url + "/" + type_ + "/" + item_id
    else:
        if not item_id.startswith(type_ + ":"):
            # Inside a json dashboard ids don't include type_
            item_id = type_ + ":" + item_id
        item_json_url = elastic.index_url + "/doc/" + item_id

        if type_ == 'dashboard':
            # Bool filters value must be true/false no 1/0 in es6
            item_json = fix_dash_bool_filters(item_json)
            # Vis height of 1 is too small for kibana6
            item_json = fix_dashboard_heights(item_json)

        if type_ == 'visualization':
            # Metric vis includes in es6 new params for the style
            item_json = add_vis_style(item_json)

        item_json = {"type": type_, type_: item_json}

    headers = HEADERS_JSON
    res = requests_ses.post(item_json_url, data=json.dumps(item_json),
                            verify=False, headers=headers)

    # Check if there is a problem with `release_date` field mapping
    # In Kibana 6 we need to add the corresponding mapping to .kibana index
    if res.status_code == 400:
        res_content = res.json()
        if res_content['error']['type'] == "strict_dynamic_mapping_exception" and \
                RELEASE_DATE in res_content['error']['reason']:

            logger.debug("Field `%s` not present in `.kibana` mapping.", RELEASE_DATE)

            # Update .kibana mapping
            res = put_release_date_mapping(elastic)
            res.raise_for_status()

            logger.debug("`.kibana` mapping updated for dashboard and index-pattern objects.")

            # retry uploading panel
            res = requests_ses.post(item_json_url, data=json.dumps(item_json),
                                    verify=False, headers=headers)

    res.raise_for_status()

    return item_json


def put_release_date_mapping(elastic):
    """Adds mapping for `release_date` field to .kibana index in Kibana 6"""
    mapping = """
    {
      "properties": {
        "dashboard": {
          "properties": {
            "release_date": {
              "type": "date"
            }
          }
        },
        "index-pattern": {
          "properties": {
            "release_date": {
              "type": "date"
            }
          }
        }
      }
    }
    """

    url = elastic.index_url + "/_mapping/doc"
    return requests_ses.put(url, data=mapping,
                            verify=False, headers=HEADERS_JSON)


def exists_dashboard(elastic_url, dash_id, es_index=None):
    """ Check if a dashboard exists """
    exists = False

    if not es_index:
        es_index = ".kibana"
    elastic = ElasticSearch(elastic_url, es_index)
    dash_data = get_dashboard_json(elastic, dash_id)
    if 'panelsJSON' in dash_data:
        exists = True

    return exists


def get_dashboard_json(elastic, dashboard_id):
    dash_json = find_item_json(elastic, "dashboard", dashboard_id)

    return dash_json


def get_vis_json(elastic, vis_id):
    vis_json = find_item_json(elastic, "visualization", vis_id)

    return vis_json


def get_search_json(elastic, search_id):
    search_json = find_item_json(elastic, "search", search_id)

    return search_json


def get_index_pattern_json(elastic, index_pattern_id):
    index_pattern_json = find_item_json(elastic, "index-pattern",
                                        index_pattern_id)

    return index_pattern_json


def get_search_from_vis(elastic, vis):
    search_id = None
    vis_json = get_vis_json(elastic, vis)
    if not vis_json:
        search_id
    # The index pattern could be in search or in state
    # First search for it in saved search
    if "savedSearchId" in vis_json:
        search_id = vis_json["savedSearchId"]
    return search_id


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


def get_index_pattern_from_search(elastic, search):
    index_pattern = None
    search_json = get_search_json(elastic, search)
    if not search_json:
        return
    if "kibanaSavedObjectMeta" in search_json:
        index_pattern = \
            get_index_pattern_from_meta(search_json["kibanaSavedObjectMeta"])
    return index_pattern


def get_index_pattern_from_vis(elastic, vis):
    index_pattern = None
    vis_json = get_vis_json(elastic, vis)
    if not vis_json:
        return
    # The index pattern could be in search or in state
    # First search for it in saved search
    if "savedSearchId" in vis_json:
        search_json = find_item_json(elastic, "search",
                                     vis_json["savedSearchId"])
        index_pattern = \
            get_index_pattern_from_meta(search_json["kibanaSavedObjectMeta"])
    elif "kibanaSavedObjectMeta" in vis_json:
        index_pattern = \
            get_index_pattern_from_meta(vis_json["kibanaSavedObjectMeta"])
    return index_pattern


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


def import_dashboard(elastic_url, kibana_url, import_file, es_index=None,
                     data_sources=None, add_vis_studies=False, strict=False):
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
        if strict:
            logger.debug("Retrieving dashboard %s to check release date.", dash_id)
            current_panel = fetch_dashboard(elastic_url, dash_id, es_index)

            # If there is no current release, that means current dashboard was created before adding release_date field
            # or panel is new in this ElasticSearch server, then import dashboard
            import_json = new_release(current_panel['dashboard'], json_to_import['dashboard'])

        if import_json:
            feed_dashboard(json_to_import, elastic_url, kibana_url, es_index, data_sources, add_vis_studies)
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
            if strict:
                logger.debug("Retrieving index pattern %s to check release date.", ip_id)
                current_ip = fetch_index_pattern(elastic_url, ip_id, es_index)

                # If there is no current release, that means current index pattern was created before adding
                # release_date field or index pattern is new in this ElasticSearch server, then import it
                import_json = new_release(current_ip, index_pattern)

            if import_json:
                feed_dashboard({"index_patterns": [index_pattern]}, elastic_url, kibana_url,
                               es_index, data_sources, add_vis_studies)
                logger.info("Index pattern %s from %s imported", ip_id, get_index_patterns_name(import_file))

            else:
                logger.warning("Index Pattern %s not imported from %s. Newer or equal version found in Kibana.",
                                ip_id, import_file)

    else:
        logger.warning("Strict mode supported only for panels and index patterns.")


def new_release(current_item, item_to_import):
    """Check whether a release is newer than another one

    :param current_release:
    :param import_release:
    :return: True if import release is newer than current one
    """

    current_release = current_item['value'].get(RELEASE_DATE)
    import_release = item_to_import['value'].get(RELEASE_DATE)

    logger.debug("Current item release date %s.", current_release)

    if not import_release:
        raise ValueError("'" + RELEASE_DATE + "' field not found in item to import.")

    logger.debug("Item to import release date %s.", import_release)

    is_new = True
    if current_release:
        import_date = dateutil.parser.parse(import_release)
        current_date = dateutil.parser.parse(current_release)

        if current_date >= import_date:
            is_new = False

    return is_new


def create_kibana_index(kibana_url):
    """
    Force the creation of the kibana index using the kibana API
    :param kibana_url: Kibana URL
    :return:
    """

    def set_kibana_setting(endpoint_url, data_value):
        set_ok = False

        try:
            res = requests_ses.post(endpoint_url, headers=ES6_HEADER,
                                    data=json.dumps(data_value), verify=False)
            res.raise_for_status()
            # With Search guard if the auth is invalid the URL is redirected to the login
            # We need to detect that and record it as an error
            if res.history and res.history[0].is_redirect:
                logging.error("Problems with search guard authentication %s" % endpoint_url)
            else:
                set_ok = True
        except requests.exceptions.HTTPError:
            logging.error("Impossible to set %s: %s", endpoint_url, str(res.json()))

        return set_ok

    kibana_settings_url = kibana_url + '/api/kibana/settings'

    # Configure the default index with the default value in Kibana
    # If the kibana index does not exists, it is created by Kibana
    endpoint = 'defaultIndex'
    data_value = {"value": None}
    endpoint_url = kibana_settings_url + '/' + endpoint

    return set_kibana_setting(endpoint_url, data_value)


def check_kibana_index(es_url, kibana_url, kibana_index=".kibana"):
    """
    Check if kibana index already exists and if not, create it

    :param es_url: Elasticsearch URL with kibana
    :param kibana_url: Kibana URL
    :param kibana_index: index with kibana information
    :return:
    """

    kibana_index_ok = False
    kibana_index_url = es_url + "/" + kibana_index

    try:
        res = requests_ses.get(kibana_index_url, verify=False)
        res.raise_for_status()
        kibana_index_ok = True
    except:
        logging.info("%s does not exist. Creating it." % kibana_index_url)
        if create_kibana_index(kibana_url):
            kibana_index_ok = True

    return kibana_index_ok


def feed_dashboard(dashboard, elastic_url, kibana_url, es_index=None, data_sources=None,
                   add_vis_studies=False):
    """ Import a dashboard. If data_sources are defined, just include items
        for this data source.
    """

    if not es_index:
        es_index = ".kibana"

    # In Kibana >= 6.1 the index could not exists
    if not check_kibana_index(elastic_url, kibana_url, es_index):
        raise RuntimeError("Kibana checks have failed")

    elastic = ElasticSearch(elastic_url, es_index)

    if 'dashboard' in dashboard:
        # Get viz titles because the are needed to check what items must be
        # excluded by data source name in case that option is enabled
        viz_titles = {}
        if 'visualizations' in dashboard:
            for visualization in dashboard['visualizations']:
                viz_id = visualization['id']
                viz_title = visualization['value']['title']
                viz_titles[viz_id] = viz_title

        import_item_json(elastic, "dashboard", dashboard['dashboard']['id'],
                         dashboard['dashboard']['value'], data_sources, add_vis_studies,
                         viz_titles=viz_titles)

    if 'searches' in dashboard:
        for search in dashboard['searches']:
            import_item_json(elastic, "search", search['id'], search['value'],
                             data_sources)

    if 'index_patterns' in dashboard:
        for index in dashboard['index_patterns']:
            if not data_sources or \
                    is_index_pattern_from_data_sources(index, data_sources):
                import_item_json(elastic, "index-pattern",
                                 index['id'], index['value'])
            else:
                logger.debug("Index pattern %s not for %s. Not included.",
                             index['id'], data_sources)

    if 'visualizations' in dashboard:
        for vis in dashboard['visualizations']:
            if not add_vis_studies and is_vis_study(vis):
                logger.debug("Vis %s is for an study. Not included.", vis['id'])
            elif not data_sources or is_vis_from_data_sources(vis, data_sources):
                import_item_json(elastic, "visualization",
                                 vis['id'], vis['value'])
            else:
                logger.debug("Vis %s not for %s. Not included.",
                             vis['id'], data_sources)


def fetch_index_pattern(elastic_url, ip_id, es_index=None):
    """
    Fetch an index pattern JSON definition from Kibana and return it.

    :param elastic_url: Elasticsearch URL
    :param ip_id: index pattern identifier
    :param es_index: kibana index
    :return: a dict with index pattern data
    """

    logger.debug("Fetching index pattern %s", ip_id)
    if not es_index:
        es_index = ".kibana"

    elastic = ElasticSearch(elastic_url, es_index)

    ip_json = get_index_pattern_json(elastic, ip_id)

    index_pattern = {"id": ip_id,
                     "value": ip_json}

    return index_pattern


def fetch_dashboard(elastic_url, dash_id, es_index=None):
    """
    Fetch a dashboard JSON definition from Kibana and return it.

    :param elastic_url: Elasticsearch URL
    :param dash_id: dashboard identifier
    :param es_index: kibana index
    :return: a dict with the dashboard data (vis, searches and index patterns)
    """

    # Kibana dashboard fields
    kibana = {"dashboard": None,
              "visualizations": [],
              "index_patterns": [],
              "searches": []}

    # Used to avoid having duplicates
    search_ids_done = []
    index_ids_done = []

    logger.debug("Fetching dashboard %s", dash_id)
    if not es_index:
        es_index = ".kibana"

    elastic = ElasticSearch(elastic_url, es_index)

    kibana["dashboard"] = {"id": dash_id,
                           "value": get_dashboard_json(elastic, dash_id)}

    if "panelsJSON" not in kibana["dashboard"]["value"]:
        # The dashboard is empty. No visualizations included.
        return kibana

    # Export all visualizations and the index patterns and searches in them
    for panel in json.loads(kibana["dashboard"]["value"]["panelsJSON"]):
        logger.debug("Analyzing panel %s (%s)", panel['id'], panel['type'])
        if panel['type'] in ['visualization']:
            vis_id = panel['id']
            vis_json = get_vis_json(elastic, vis_id)
            kibana["visualizations"].append({"id": vis_id, "value": vis_json})
            search_id = get_search_from_vis(elastic, vis_id)
            if search_id and search_id not in search_ids_done:
                search_ids_done.append(search_id)
                kibana["searches"].append(
                    {"id": search_id,
                     "value": get_search_json(elastic, search_id)}
                    )
            index_pattern_id = get_index_pattern_from_vis(elastic, vis_id)
            if index_pattern_id and index_pattern_id not in index_ids_done:
                index_ids_done.append(index_pattern_id)
                kibana["index_patterns"].append(
                    {"id": index_pattern_id,
                     "value": get_index_pattern_json(elastic,
                                                     index_pattern_id)}
                    )
        elif panel['type'] in ['search']:
            # A search could be directly visualized inside a panel
            search_id = panel['id']
            kibana["searches"].append(
                {"id": search_id,
                 "value": get_search_json(elastic, search_id)}
                )
            index_pattern_id = get_index_pattern_from_search(elastic,
                                                             search_id)
            if index_pattern_id and index_pattern_id not in index_ids_done:
                index_ids_done.append(index_pattern_id)
                kibana["index_patterns"].append(
                    {"id": index_pattern_id,
                     "value": get_index_pattern_json(elastic,
                                                     index_pattern_id)}
                    )

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

                index_pattern['value'][RELEASE_DATE] = dt.utcnow().isoformat()
                index_pattern_importable = {"index_patterns": [index_pattern]}
                with open(export_file_index, 'w') as f:
                    f.write(json.dumps(index_pattern_importable, indent=4, sort_keys=True))


def export_dashboard(elastic_url, dash_id, export_file, es_index=None, split_index_patterns=False):
    """
    Export a dashboard from Kibana to a file in JSON format. If split_index_patterns is defined it will
    store the index patterns in separate files.

    :param elastic_url: Elasticsearch URL
    :param dash_id: dashboard identifier
    :param export_file: name of the file in which to export the dashboard
    :param es_index: name of the Kibana index
    :param split_index_patterns: store the index patterns in separate files
    """

    logger.debug("Exporting dashboard %s to %s", dash_id, export_file)

    kibana = fetch_dashboard(elastic_url, dash_id, es_index)

    # Add release date to identify this particular version of the panel
    kibana['dashboard']['value'][RELEASE_DATE] = dt.utcnow().isoformat()

    export_dashboard_files(kibana, export_file, split_index_patterns)

    logger.debug("Done")
