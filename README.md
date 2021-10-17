localstack-plugin-loader
========================

<p>
  <a href="https://pypi.org/project/localstack-plugin-loader/"><img alt="PyPI Version" src="https://img.shields.io/pypi/v/localstack-plugin-loader?color=blue"></a>
  <a href="https://img.shields.io/pypi/l/localstack-plugin-loader.svg"><img alt="PyPI License" src="https://img.shields.io/pypi/l/localstack-plugin-loader.svg"></a>
  <a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

localstack-plugin-loader is the dynamic code loading framework used in [LocalStack](https://github.com/localstack/localstack).

Install
-------

    pip install localstack-plugin-loader

Develop
-------

Create the virtual environment, install dependencies, and run tests

    make venv
    make test

Run the code formatter

    make format

Upload the pypi package using twine

    make upload
