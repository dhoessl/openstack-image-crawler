#!/usr/bin/env python3
#
# image crawler
#
# the image crawler checks for new openstack ("cloud") images
# whenever a new image is detected all relevant information needed for
# maintaining an image catalog
#
# 2023-06-11 v0.4.0 christian.stelter@plusserver.com

import sys
import os
from loguru import logger
from crawler.core.args import get_args
from crawler.core.config import config_read
from crawler.core.database import (
    database_connect, database_disconnect, database_initialize
)
from crawler.core.exporter import export_image_catalog, export_image_catalog_all
from crawler.core.main import crawl_image_sources
from crawler.git.base import clone_or_pull, update_repository


def define_logger(debug: bool) -> None:
    log_level = "INFO"
    log_format = (
        "<level>{message}</level>"
    )
    if debug:
        log_level = "DEBUG"
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}:{function}</cyan>:<cyan>{line}</cyan> "
            "- <level>{message}</level>"
        )
    logger.remove()
    logger.add(sys.stderr, format=log_format, level=log_level, colorize=True)
    logger.info("plusserver Image Crawler v0.4.0 started")


def get_config(config_file, sources_file) -> tuple:
    # read config file
    config = config_read(config_file, "configuration")
    if config is None:
        raise SystemExit(1)

    # read the image sources
    if sources_file is not None:
        sources_filename = sources_file
    else:
        sources_filename = config["sources_name"]
    image_source_catalog = config_read(sources_filename, "image source catalog")
    if image_source_catalog is None:
        raise SystemExit(1)

    return (config, image_source_catalog)


def clone_or_update_repo(config: dict, git_ssh_command) -> str:
    if "branch" in config:
        working_branch = config["branch"]
    else:
        working_branch = "main"
    clone_or_pull(
        config["remote_repository"],
        config["local_repository"],
        working_branch,
        git_ssh_command
    )


def main() -> None:
    working_directory = os.getcwd()
    program_directory = os.path.dirname(os.path.abspath(__file__))

    args = get_args(program_directory)
    define_logger(args.debug)

    config, image_source_catalog = get_config(args.config, args.sources)

    # initialize database when run with --init-db
    if args.init_db:
        database_initialize(config["database_name"], program_directory)
        sys.exit(0)

    # set git_ssh_command if set in config
    if "git_ssh_command" in config:
        git_ssh_command = config["git_ssh_command"]
    else:
        git_ssh_command = None

    # clone or update local repository when git is enabled
    if "remote_repository" in config:
        clone_or_update_repo(config, git_ssh_command)
    else:
        logger.warning("No image catalog repository configured")

    # connect to database
    database = database_connect(config["database_name"])
    if database is None:
        raise ValueError(
            "No database connected. Run './image-crawler.py --init-db' to "
            f"create new database OR check your config at {args.config}."
        )

    # crawl image sources when requested
    if args.export_only:
        logger.info("Skipping repository crawling")
        updated_sources = {}
    else:
        logger.info("Start repository crawling")
        updated_sources = crawl_image_sources(image_source_catalog, database)

    # skip export image catalog if updates_only flag is set
    if args.updates_only:
        logger.info("Skipping catalog export")
        database_disconnect(database)
        return None

    # export image catalog
    if config["local_repository"].startswith("/"):
        export_path = config["local_repository"]
    else:
        export_path = os.path.join(
            working_directory, config["local_repository"]
        )

    if updated_sources:
        logger.info(f"Exporting catalog to {export_path}")
        export_image_catalog(
            database,
            image_source_catalog,
            updated_sources,
            config["local_repository"],
            config["template_path"],
        )
        # push changes to git repository when configured
        if "remote_repository" in config:
            update_repository(
                database, config["local_repository"],
                updated_sources, git_ssh_command
            )
        else:
            logger.info("No remote repository update needed.")
    if not updated_sources and args.export_only:
        logger.info(f"Exporting all catalog files to {export_path}")
        export_image_catalog_all(
            database,
            image_source_catalog,
            config["local_repository"],
            config["template_path"],
        )
    database_disconnect(database)


if __name__ == "__main__":
    main()
