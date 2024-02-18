"""
A plux frontend, currently only supports setuptools.
"""

import argparse
import json
import logging
import os

from plux.build.setuptools import (
    _get_egg_info_dir,
    find_plugins,
    get_distribution_from_workdir,
    get_plux_json_path,
)


def entrypoints(args):
    dist = get_distribution_from_workdir(args.workdir)

    print("discovering plugins ...")
    dist.run_command("plugins")

    print(f"building {dist.get_name().replace('-', '_')}.egg-info...")
    dist.run_command("egg_info")

    print("discovered plugins:")
    # discover plux plugins
    with open(get_plux_json_path(dist)) as fd:
        plux_json = json.load(fd)
    _pprint_plux_json(plux_json)


def discover(args):
    ep = find_plugins(exclude=("tests", "tests.*"))  # TODO: options
    _pprint_plux_json(ep)


def show(args):
    egg_info_dir = _get_egg_info_dir()
    if not egg_info_dir:
        print("no *.egg-info directory")
        return

    txt = os.path.join(egg_info_dir, "entry_points.txt")
    if not os.path.isfile(txt):
        print("no entry points to show")
        return

    with open(txt) as fd:
        print(fd.read())


def _pprint_plux_json(plux_json):
    print(json.dumps(plux_json, indent=2))


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
    generate_parser = subparsers.add_parser(
        "entrypoints", help="Discover plugins and generate entry points"
    )
    generate_parser.set_defaults(func=entrypoints)

    # Subparser for the 'discover' subcommand
    discover_parser = subparsers.add_parser("discover", help="Discover plugins and print them")
    discover_parser.set_defaults(func=discover)

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
