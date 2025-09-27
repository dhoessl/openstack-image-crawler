#!/usr/bin/env python3
#
# image crawler
#
# image crawler checks for new images which are defined in the provided
# config file. The image catalog is updated with information from config
# and image url
#
# 2023-06-11 v0.4.0 christian.stelter@plusserver.com
# 2025-09-24 v0.5.0 dominic.hoessl@gmail.com

import sys
import os
from loguru import logger
from crawler.core.args import get_args
from crawler.core.config import config_read
from crawler.core.database import Database
from crawler.core.exporter import Exporter
from crawler.core.main import crawl_image_sources, crawl_back_image_sources
from crawler.git.base import clone_or_pull, update_repository


def define_logger(debug: bool, branding: str) -> None:
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
    # TODO: fetch version from somewhere
    logger.info(f"{branding} Image Crawler v0.5.0 started")


def get_config(config_file, sources_file) -> tuple:
    # read config file
    config = config_read(config_file, "configuration")
    if config is None:
        raise RuntimeError("Configuration was not created")

    # read the image sources
    if sources_file is not None:
        sources_filename = sources_file
    else:
        sources_filename = config["sources_name"]
    image_source_catalog = config_read(sources_filename, "image source catalog")
    if image_source_catalog is None:
        raise RuntimeError("Image source catalog could not been created")

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
    program_directory = os.path.dirname(os.path.abspath(__file__))

    args = get_args(program_directory)
    define_logger(args.debug, args.branding_name)

    config, image_source_catalog = get_config(args.config, args.sources)

    # initialize database when run with --init-db
    if args.init_db:
        database = Database(config["database_name"], init=True)
        database.init_db(program_directory)
        return None  # Exit if database was created

    # set git_ssh_command if set in config
    if "git_ssh_command" in config:
        git_ssh_command = config["git_ssh_command"]
    else:
        git_ssh_command = None

    # create export_path
    if config["local_repository"].startswith("/"):
        export_path = config["local_repository"]
    else:
        export_path = os.path.join(
            os.getcwd(), config["local_repository"]
        )
    # clone or update local repository when git is enabled
    if "remote_repository" in config:
        clone_or_update_repo(config, git_ssh_command)
    else:
        logger.warning("No image catalog repository configured")

    # connect to database
    database = Database(config["database_name"])
    if not database.is_alive():
        raise RuntimeError(
            "Database is not connected. "
            f"Please check your config at {args.config}"
        )
    # Check if database pragma is up to date
    database.update()

    if args.updates_only:
        # Only Update Sources and repository
        logger.info("Start repository crawling")
        updated_sources = crawl_image_sources(image_source_catalog, database)
        logger.info("Only Updates - No catalog export")
        if "remote_repository" in config and updated_sources:
            update_repository(
                database, config["local_repository"],
                updated_sources, git_ssh_command
            )
        else:
            logger.info("No remote repository update needed!")
    elif args.export_only:
        # Only Export existing config to files
        logger.info("Export Only - Skip repository crawling")
        exporter = Exporter(
            database, image_source_catalog, {},
            config["local_repository"], config["template_path"]
        )
        logger.info(f"Exporting all catalog files to {export_path}")
        exporter.export_image_catalog()
    elif args.crawl_back:
        # Crawl back images up to the limit defined for an image
        logger.info("Start historic repository crawling")
        updated_sources = crawl_back_image_sources(
            image_source_catalog, database
        )
    else:
        # no switches from update_exclusive_group
        # do the normal image update
        logger.info("Start repository crawling")
        updated_sources = crawl_image_sources(image_source_catalog, database)
        exporter = Exporter(
            database, image_source_catalog, updated_sources,
            config["local_repository"], config["template_path"]
        )
        logger.info(f"Exporting catalog to {export_path}")
        exporter.export_image_catalog()
        if "remote_repository" in config and updated_sources:
            update_repository(
                database, config["local_repository"],
                updated_sources, git_ssh_command
            )
        else:
            logger.info("No remote repository update needed!")
    database.disconnect()


if __name__ == "__main__":
    main()
