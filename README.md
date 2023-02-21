Plux
====

<p>
  <a href="https://github.com/localstack/plux/actions/workflows/build.yml"><img alt="CI badge" src="https://github.com/localstack/plux/actions/workflows/build.yml/badge.svg"></img></a>
  <a href="https://pypi.org/project/plux/"><img alt="PyPI Version" src="https://img.shields.io/pypi/v/plux?color=blue"></a>
  <a href="https://img.shields.io/pypi/l/plux.svg"><img alt="PyPI License" src="https://img.shields.io/pypi/l/plux.svg"></a>
  <a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

plux is the dynamic code loading framework used in [LocalStack](https://github.com/localstack/localstack).


Overview
--------

Plux builds a higher-level plugin mechanism around [Python's entry point mechanism](https://packaging.python.org/specifications/entry-points/).
It provides tools to load plugins from entry points at run time, and to discover entry points from plugins at build time (so you don't have to declare entry points statically in your `setup.py`).

### Core concepts

* `PluginSpec`: describes a `Plugin`. Each plugin has a namespace, a unique name in that namespace, and a `PluginFactory` (something that creates `Plugin` the spec is describing.
  In the simplest case, that can just be the Plugin's class).
* `Plugin`: an object that exposes a `should_load` and `load` method.
  Note that it does not function as a domain object (it does not hold the plugins lifecycle state, like initialized, loaded, etc..., or other metadata of the Plugin)
* `PluginFinder`: finds plugins, either at build time (by scanning the modules using `pkgutil` and `setuptools`) or at run time (reading entrypoints of the distribution using [stevedore](https://docs.openstack.org/stevedore/latest/))
* `PluginManager`: manages the run time lifecycle of a Plugin, which has three states:
  * resolved: the entrypoint pointing to the PluginSpec was imported and the `PluginSpec` instance was created
  * init: the `PluginFactory` of the `PluginSpec` was successfully invoked
  * loaded: the `load` method of the `Plugin` was successfully invoked

![architecture](https://raw.githubusercontent.com/localstack/plux/main/docs/plux-architecture.png)

### Loading Plugins

At run time, a `PluginManager` uses a `PluginFinder` that in turn uses stevedore to scan the available entrypoints for things that look like a `PluginSpec`.
With `PluginManager.load(name: str)` or `PluginManager.load_all()`, plugins within the namespace that are discoverable in entrypoints can be loaded.
If an error occurs at any state of the lifecycle, the `PluginManager` informs the `PluginLifecycleListener` about it, but continues operating.

### Discovering entrypoints

To build a source distribution and a wheel of your code with your plugins as entrypoints, simply run `python setup.py plugins sdist bdist_wheel`.

How it works:
For discovering plugins at build time, plux provides a custom setuptools command `plugins`, invoked via `python setup.py plugins`.
The command uses a special `PluginFinder` that collects from the codebase anything that can be interpreted as a `PluginSpec`, and creates from it a plugin index file `plux.json`, that is placed into the `.egg-info` distribution metadata directory.
When a setuptools command is used to create the distribution (e.g., `python setup.py sdist/bdist_wheel/...`), plux finds the `plux.json` plugin index and extends automatically the list of entry points (collected into `.egg-info/entry_points.txt`).
The `plux.json` file becomes a part of the distribution, s.t., the plugins do not have to be discovered every time your distribution is installed elsewhere.



Examples
--------

To build something using the plugin framework, you will first want to introduce a Plugin that does something when it is loaded.
And then, at runtime, you need a component that uses the `PluginManager` to get those plugins.

### One class per plugin

This is the way we went with `LocalstackCliPlugin`. Every plugin class (e.g., `ProCliPlugin`) is essentially a singleton.
This is easy, as the classes are discoverable as plugins.
Simply create a Plugin class with a name and namespace and it will be discovered by the build time `PluginFinder`.

```python

# abstract case (not discovered at build time, missing name)
class CliPlugin(Plugin):
    namespace = "my.plugins.cli"

    def load(self, cli):
        self.attach(cli)

    def attach(self, cli):
        raise NotImplementedError

# discovered at build time (has a namespace, name, and is a Plugin)
class MyCliPlugin(CliPlugin):
    name = "my"

    def attach(self, cli):
        # ... attach commands to cli object

```

now we need a `PluginManager` (which has a generic type) to load the plugins for us:

```python
cli = # ... needs to come from somewhere

manager: PluginManager[CliPlugin] = PluginManager("my.plugins.cli", load_args=(cli,))

plugins: List[CliPlugin] = manager.load_all()

# todo: do stuff with the plugins, if you want/need
#  in this example, we simply use the plugin mechanism to run a one-shot function (attach) on a load argument

```

### Re-usable plugins

When you have lots of plugins that are structured in a similar way, we may not want to create a separate Plugin class
for each plugin. Instead we want to use the same `Plugin` class to do the same thing, but use several instances of it.
The `PluginFactory`, and the fact that `PluginSpec` instances defined at module level are discoverable (inpired
by [pluggy](https://github.com/pytest-dev/pluggy)), can be used to achieve that.

```python

class ServicePlugin(Plugin):

    def __init__(self, service_name):
        self.service_name = service_name
        self.service = None

    def should_load(self):
        return self.service_name in config.SERVICES

    def load(self):
        module = importlib.import_module("localstack.services.%s" % self.service_name)
        # suppose we define a convention that each service module has a Service class, like moto's `Backend`
        self.service = module.Service()

def service_plugin_factory(name) -> PluginFactory:
    def create():
        return ServicePlugin(name)

    return create

# discoverable
s3 = PluginSpec("localstack.plugins.services", "s3", service_plugin_factory("s3"))

# discoverable
dynamodb = PluginSpec("localstack.plugins.services", "dynamodb", service_plugin_factory("dynamodb"))

# ... could be simplified with convenience framework code, but the principle will stay the same

```

Then we could use the `PluginManager` to build a Supervisor

```python

class Supervisor:
    manager: PluginManager[ServicePlugin]

    def start(self, service_name):
        plugin = manager.load(service_name)
        service = plugin.service
        service.start()

```

### Functions as plugins

with the `@plugin` decorator, you can expose functions as plugins. They will be wrapped by the framework
into `FunctionPlugin` instances, which satisfy both the contract of a Plugin, and that of the function.

```python
from plugin import plugin


@plugin(namespace="localstack.configurators")
def configure_logging(runtime):
    logging.basicConfig(level=runtime.config.loglevel)

    
@plugin(namespace="localstack.configurators")
def configure_somethingelse(runtime):
    # do other stuff with the runtime object
    pass
```

With a PluginManager via `load_all`, you receive the `FunctionPlugin` instances, that you can call like the functions

```python

runtime = LocalstackRuntime()

for configurator in PluginManager("localstack.configurators").load_all():
    configurator(runtime)
```

Configuring your distribution
-----------------------------

If you are building a python distribution that exposes plugins discovered by plux, you need to configure your projects build system so other dependencies creates the `entry_points.txt` file when installing your distribution.

For a [`pyproject.toml`](https://pip.pypa.io/en/stable/reference/build-system/pyproject-toml/) template this involves adding the `build-system` section:

```toml
[build-system]
requires = ['setuptools', 'wheel', 'plux>=1.3.1']
build-backend = "setuptools.build_meta"

# ...
```

Install
-------

    pip install plux

Develop
-------

Create the virtual environment, install dependencies, and run tests

    make venv
    make test

Run the code formatter

    make format

Upload the pypi package using twine

    make upload
