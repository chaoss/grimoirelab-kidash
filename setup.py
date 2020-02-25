#!/usr/bin/env python
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
#     Santiago Dueñas <sduenas@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@bitergia.com>
#

import codecs
import os
import re

# Always prefer setuptools over distutils
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))
readme_md = os.path.join(here, 'README.md')
version_py = os.path.join(here, 'kidash', '_version.py')

# Get the package description from the README.md file
with codecs.open(readme_md, encoding='utf-8') as f:
    long_description = f.read()

with codecs.open(version_py, 'r', encoding='utf-8') as fd:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                        fd.read(), re.MULTILINE).group(1)

setup(name="kidash",
      description="GrimoireLab script to manage " +
      "Kibana dashboards from the command line",
      long_description=long_description,
      long_description_content_type='text/markdown',
      url="https://github.com/chaoss/grimoirelab-kidash",
      version=version,
      author="Bitergia",
      author_email="grimoirelab-discussions@lists.linuxfoundation.org",
      license="GPLv3",
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Intended Audience :: Developers',
          'Topic :: Software Development',
          'License :: OSI Approved :: ' +
          'GNU General Public License v3 or later (GPLv3+)',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6'],
      keywords="development repositories analytics",
      packages=['kidash'],
      python_requires='>=3.4',
      setup_requires=['wheel'],
      extras_require={},
      tests_require=[],
      test_suite='tests',
      scripts=["bin/kidash"],
      install_requires=['python-dateutil',
                        'requests==2.21.0',
                        'urllib3==1.24.3'
                        ],
      include_package_data=True,
      zip_safe=False
      )
