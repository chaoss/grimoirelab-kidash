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
#     Alvaro del Castillo <acs@bitergia.com>
import json
import logging
import os
import sys
import shutil
import tempfile
import unittest

# Hack to make sure that tests import the right packages
# due to setuptools behaviour
sys.path.insert(0, '..')

from kidash.kidash import export_dashboard_files

OVERVIEW_DASH_FILE = 'data/overview-with-index-patterns.json'


class TestReport(unittest.TestCase):
    """Basic tests for the Report class """

    def test_export_split_index_patterns(self):
        """Test whether a dashboard is exported with index patterns in separate files"""

        # Expected file names to be exported
        dashboard_file = "overview.json"
        index_patterns_files = ["github_issues-index-pattern.json", "git-index-pattern.json",
                                "mbox-index-pattern.json"]

        tmpdir = tempfile.mkdtemp(prefix='kidash_')
        export_file = os.path.join(tmpdir, "overview.json")
        split_index_patterns = True

        with open(OVERVIEW_DASH_FILE) as fdash:
            overview = json.load(fdash)
            export_dashboard_files(overview, export_file, split_index_patterns)
            self.assertTrue(set(os.listdir(tmpdir)) == set([dashboard_file] + index_patterns_files))

        shutil.rmtree(tmpdir)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main(buffer=True, warnings='ignore')
