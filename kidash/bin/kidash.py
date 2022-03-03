#!/usr/bin/env python3
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

import argparse
import logging

from requests import HTTPError

from kidash.kidash import import_dashboard, export_dashboard, list_dashboards


def main():

    args = get_params()

    config_logging(args.debug)

    try:
        if args.import_file:
            import_dashboard(args.elastic_url, args.kibana_url, args.import_file, args.kibana_index,
                             args.data_sources, args.add_vis_studies, args.strict)
        elif args.export_file:
            if args.dashboard:
                export_dashboard(args.elastic_url, args.dashboard, args.export_file,
                                 args.kibana_index, args.split_index_patterns)
        elif args.list:
            list_dashboards(args.elastic_url, args.kibana_index)

    except HTTPError as http_error:
        res = http_error.response
        error_msg = u'%s. Content: %s' % (http_error, res.content)
        logging.error(error_msg)

    except ValueError as value_error:
        logging.error(value_error)

    except RuntimeError as runtime_error:
        logging.error(runtime_error)


def get_params_parser_create_dash():
    """Parse command line arguments"""

    parser = argparse.ArgumentParser(usage="usage: kidash [options]",
                                     description="Import or Export a Kibana Dashboard")

    parser.add_argument("-e", "--elastic_url", default="http://127.0.0.1:9200",
                        help="Host with elastic search (default: http://127.0.0.1:9200)")

    parser.add_argument("--dashboard", help="Kibana dashboard id to export")
    parser.add_argument("--split-index-patterns", action='store_true',
                        help="Kibana index patterns are exported in different files")
    parser.add_argument("--export", dest="export_file", help="file with the dashboard exported")

    parser.add_argument("--import", dest="import_file", help="file with the dashboard/index pattern to be imported")
    parser.add_argument("--strict", action="store_true", help="check release date and only import newer panels")
    parser.add_argument("--kibana", dest="kibana_index", default=".kibana", help="Kibana index name (.kibana default)")
    parser.add_argument("--list", action='store_true', help="list available dashboards")
    parser.add_argument('-g', '--debug', dest='debug', action='store_true')
    parser.add_argument("--data-sources", nargs='+', dest="data_sources", help="Data sources to be included")
    parser.add_argument("--add-vis-studies", dest="add_vis_studies",
                        action='store_true', help="Include visualizations for studies")
    parser.add_argument("--kibana-url", dest="kibana_url", default="http://localhost:5601",
                        help="Kibana URL (http://localhost:5601 by default)")

    return parser


def get_params():
    parser = get_params_parser_create_dash()
    args = parser.parse_args()

    if not (args.export_file or args.import_file or args.list):
        parser.error("--export or --import or --list needed")
    else:
        if args.export_file and not args.dashboard:
            parser.error("--export needs --dashboard")
    return args


def config_logging(debug):

    if debug:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')
        logging.debug("Debug mode activated")
    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


if __name__ == '__main__':
    main()
