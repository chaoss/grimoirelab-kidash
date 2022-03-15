# Kidash [![Build Status](https://github.com/chaoss/grimoirelab-kidash/workflows/tests/badge.svg)](https://github.com/chaoss/grimoirelab-kidash/actions?query=workflow:tests+branch:master+event:push) [![Coverage Status](https://img.shields.io/coveralls/chaoss/grimoirelab-kidash.svg)](https://coveralls.io/r/chaoss/grimoirelab-kidash?branch=master)

Kidash is a tool for managing Kibana-related dashboards from the command line. The standard GrimoireLab dashboards
are available in the [Sigils](https://github.com/chaoss/grimoirelab-sigils) repository.

## Installation

You can set up a virtual environment where Kidash will be installed
```
python3 -m venv foo
source bin foo/bin/activate
```

* Using PyPi
```buildoutcfg
pip3 install kidash
```

* From Source code
```buildoutcfg
git clone https://github.com/chaoss/grimoirelab-kidash
cd grimoirelab-kidash
python3 setup.py install
```

## Usage

- Get a list of all options with:
```
$ kidash --help
```

- Import a dashboard:
```buildoutcfg
kidash -g -e <elasticsearch-url>:<port> --import <local-file-path>
example: kidash -g -e https://admin:admin@localhost:9200 --import ./overview.json
```

- Export a dashboard:
```buildoutcfg
kidash -g -e <elasticsearch-url> --dashboard <dashboard-id>* --export <local-file-path> --split-index-pattern
example: kidash -g -e https://admin:admin@localhost:9200 --dashboard overview --export overview.json
```
