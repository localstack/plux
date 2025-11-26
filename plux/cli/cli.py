"""
A plux CLI frontend. Currently it heavily relies on setuptools, but should be extended in the future to support other
build backends like hatchling or poetry.
"""

import argparse
import logging
import os
import sys

from plux.build import config
from plux.build.project import Project

LOG = logging.getLogger(__name__)


def _get_build_backend() -> str | None:
    # TODO: should read this from the project configuration instead somehow.
    try:
        import setuptools  # noqa

        return "setuptools"
    except ImportError:
        pass

    try:
        import hatchling  # noqa

        return "hatchling"
    except ImportError:
        pass

    return None


def _load_project(args: argparse.Namespace) -> Project:
    backend = _get_build_backend()
    workdir = args.workdir

    if args.verbose:
        print(f"loading project config from {workdir}, determined build backend is: {backend}")

    if backend == "setuptools":
        from plux.build.setuptools import SetuptoolsProject

        return SetuptoolsProject(workdir)
    elif backend == "hatchling":
        raise NotImplementedError("Hatchling is not yet supported as build backend")
    else:
        raise RuntimeError(
            "No supported build backend found. Plux needs either setuptools or hatchling to work."
        )


def entrypoints(args: argparse.Namespace):
    project = _load_project(args)
    project.config = project.config.merge(
        exclude=args.exclude.split(",") if args.exclude else None,
        include=args.include.split(",") if args.include else None,
    )
    cfg = project.config

    print(f"entry point build mode: {cfg.entrypoint_build_mode.value}")

    if cfg.entrypoint_build_mode == config.EntrypointBuildMode.BUILD_HOOK:
        print("discovering plugins and building entrypoints automatically...")
        project.build_entrypoints()
    elif cfg.entrypoint_build_mode == config.EntrypointBuildMode.MANUAL:
        path = os.path.join(os.getcwd(), cfg.entrypoint_static_file)
        print(f"discovering plugins and writing to {path} ...")
        builder = project.create_plugin_index_builder()
        with open(path, "w") as fd:
            builder.write(fd, output_format="ini")


def discover(args: argparse.Namespace):
    project = _load_project(args)
    project.config = project.config.merge(
        path=args.path,
        exclude=args.exclude.split(",") if args.exclude else None,
        include=args.include.split(",") if args.include else None,
    )

    builder = project.create_plugin_index_builder()
    builder.write(fp=args.output, output_format=args.format)


def show(args: argparse.Namespace):
    project = _load_project(args)

    try:
        entrypoints_file = project.find_entry_point_file()
    except FileNotFoundError as e:
        print(f"Entrypoints file could not be located: {e}")
        return

    if not entrypoints_file.exists():
        print(f"No entrypoints file found at {entrypoints_file}, nothing to show")
        return

    print(entrypoints_file.read_text())


def resolve(args):
    for p in sys.path:
        print(f"path = {p}")
    from plux import PluginManager

    manager = PluginManager(namespace=args.namespace)

    for spec in manager.list_plugin_specs():
        print(f"{spec.namespace}:{spec.name} = {spec.factory.__module__}:{spec.factory.__name__}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Plux CLI frontend")
    parser.add_argument(
        "--workdir",
        type=str,
        default=os.getcwd(),
        help="overwrite the working directory",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="enable verbose logging")
    subparsers = parser.add_subparsers(title="commands", dest="command", help="Available commands")

    # Subparser for the 'generate' subcommand
    generate_parser = subparsers.add_parser("entrypoints", help="Discover plugins and generate entry points")
    generate_parser.add_argument(
        "-e",
        "--exclude",
        help="a sequence of paths to exclude; '*' can be used as a wildcard in the names. 'foo.*' will exclude all subpackages of 'foo' (but not 'foo' itself).",
    )
    generate_parser.add_argument(
        "-i",
        "--include",
        help="a sequence of paths to include; If it's specified, only the named items will be included. If it's not "
        "specified, all found items in the path will be included. 'include' can contain shell style wildcard "
        "patterns just like 'exclude'",
    )
    generate_parser.set_defaults(func=entrypoints)

    # Subparser for the 'discover' subcommand
    discover_parser = subparsers.add_parser("discover", help="Discover plugins and print them")
    discover_parser.add_argument(
        "-p",
        "--path",
        help="the file path where to look for plugins'",
    )
    discover_parser.add_argument(
        "-e",
        "--exclude",
        help="a sequence of paths to exclude; '*' can be used as a wildcard in the names. 'foo.*' will exclude all subpackages of 'foo' (but not 'foo' itself).",
    )
    discover_parser.add_argument(
        "-i",
        "--include",
        help="a sequence of paths to include; If it's specified, only the named items will be included. If it's not "
        "specified, all found items in the path will be included. 'include' can contain shell style wildcard "
        "patterns just like 'exclude'",
    )
    discover_parser.add_argument(
        "-f",
        "--format",
        help="the format in which to output the entrypoints. can be 'json' or 'ini', defaults to 'dict'.",
        default="json",
        choices=["json", "ini"],
    )
    discover_parser.add_argument(
        "-o",
        "--output",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="Output file path, defaults to stdout",
    )
    discover_parser.set_defaults(func=discover)

    # Subparser for the 'resolve' subcommand
    resolve_parser = subparsers.add_parser(
        "resolve", help="Resolve a plugin namespace and list all its plugins"
    )
    resolve_parser.add_argument("--namespace", help="the plugin namespace", required=True)
    resolve_parser.set_defaults(func=resolve)

    # Subparser for the 'discover' subcommand
    show_parser = subparsers.add_parser("show", help="Show entrypoints that were generated")
    show_parser.set_defaults(func=show)

    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    os.chdir(args.workdir)

    if not hasattr(args, "func"):
        parser.print_help()
        exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
