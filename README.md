# Kidash [![Build Status](https://github.com/chaoss/grimoirelab-kidash/workflows/tests/badge.svg)](https://github.com/chaoss/grimoirelab-kidash/actions?query=workflow:tests+branch:main+event:push) [![Coverage Status](https://img.shields.io/coveralls/chaoss/grimoirelab-kidash.svg)](https://coveralls.io/r/chaoss/grimoirelab-kidash?branch=main) [![PyPI version](https://badge.fury.io/py/kidash.svg)](https://badge.fury.io/py/kidash)

Kidash is a tool for managing Kibana-related dashboards from the command line. The standard GrimoireLab dashboards
are available in the [Sigils](https://github.com/chaoss/grimoirelab-sigils) repository.

## Requirements

 * Python >= 3.9

You will also need some other libraries for running the tool, you can find the
whole list of dependencies in [pyproject.toml](pyproject.toml) file.

## Installation

There are several ways to install Kidash on your system: packages or source 
code using Poetry or pip.

### PyPI:

Kidash can be installed using pip, a tool for installing Python packages. 
To do it, run the next command:
```
$ pip install kidash
```

### Source code

To install from the source code you will need to clone the repository first:
```
$ git clone https://github.com/chaoss/grimoirelab-kidash
$ cd grimoirelab-kidash
```

Then use pip or Poetry to install the package along with its dependencies.

#### Pip
To install the package from local directory run the following command:
```
$ pip install .
```
In case you are a developer, you should install kidash in editable mode:
```
$ pip install -e .
```

#### Poetry
We use [poetry](https://python-poetry.org/) for dependency management and 
packaging. You can install it following its [documentation](https://python-poetry.org/docs/#installation).
Once you have installed it, you can install kidash and the dependencies:
```
$ poetry install
```
To spaw a new shell within the virtual environment use:
```
$ poetry shell
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

## License

Licensed under GNU General Public License (GPL), version 3 or later.
