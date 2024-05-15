# this module fails when importing to test the fault tolerance of the plugin discovery mechanism
from plux import Plugin


def fail():
    raise ValueError("this is an expected exception")


class CannotBeLoadedPlugin(Plugin):
    namespace = "namespace_2"
    name = "cannot-be-loaded"


fail()
