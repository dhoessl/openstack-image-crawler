from argparse import ArgumentParser, Namespace


def get_args(program_directory: str) -> Namespace:
    parser = ArgumentParser(
        description="checks cloud image repositories for new updates and"
        + " keeps track of all images within its sqlite3 database"
    )
    parser.add_argument(
        "--config",
        type=str,
        required=False,
        default=f"{program_directory}/etc/config.yaml",
        help=f"specify the config file to be used \
            (default: {program_directory}/etc/config.yaml)"
    )
    parser.add_argument(
        "--sources",
        type=str,
        required=False,
        help="specify the sources file to be used \
            - overrides value from config file"
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        required=False,
        help="initialize image catalog database"
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        required=False,
        help="export only existing image catalog"
    )
    parser.add_argument(
        "--updates-only",
        action="store_true",
        required=False,
        help="check only for updates, do not export catalog"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        required=False,
        help="give more output for debugging"
    )
    parser.add_argument(
        "--branding-name",
        default="plusserver",
        help="branding name the logger displays"
    )
    return parser.parse_args()
