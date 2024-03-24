from plugin import Plugin, PluginSpec, plugin


# this is not a discoverable plugin (no name and namespace specified)
class AbstractSamplePlugin(Plugin):
    pass


# this plugin is discoverable since it can be resolved into a PluginSpec
class SimplePlugin(AbstractSamplePlugin):
    namespace = "namespace_2"
    name = "simple"

    invoked: bool = False

    def load(self):
        self.invoked = True


plugin_spec_1 = PluginSpec("namespace_1", "plugin_1", AbstractSamplePlugin)
plugin_spec_2 = PluginSpec("namespace_1", "plugin_2", AbstractSamplePlugin)

some_member = "this string should not be interpreted as a plugin"


@plugin(namespace="namespace_3")
def plugin_3():
    # this plugin is discoverable via the FunctionPlugin decorator
    return "foobar"


@plugin(name="plugin_4", namespace="namespace_3")
def functional_plugin():
    return "another"


def load_condition():
    return False


@plugin(name="plugin_5", namespace="namespace_4", should_load=lambda: load_condition())
def functional_plugin_with_load_condition_function():
    return "not loading this one"


@plugin(name="plugin_6", namespace="namespace_4", should_load=False)
def functional_plugin_with_load_condition_bool():
    return "not loading this one either"
