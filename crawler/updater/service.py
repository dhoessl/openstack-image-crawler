# service.py

# providing core functionality for the crawler in updating and crawling images

from os import path
from loguru import logger

from crawler.core.database import Database
from crawler.core.web import url_fetch_links
from crawler.updater.update_check import (
    ImageUpdateChecker,
    ImageUpdateCrawler
)
from crawler.updater.pattern import get_release_folder_pattern


def image_update_service(database: Database, source: dict) -> list:
    updated_releases = []
    for release in source["releases"]:
        # Check if release is supported. If its no supported exception will be
        # raised.
        check_release(release["image"]["distro"], source["name"])
        # Fetch last saved checksum
        last_checksum = database.get_last_checksum(
            source["name"], release["name"]
        )
        if not last_checksum:
            # Set checksum to none if there is no checksum for the release
            last_checksum = f"{release['checksum']['algorithm']}:none"
        logger.debug("last_checksum:" + last_checksum)
        # create Updater Object and run an update check
        updater = ImageUpdateChecker(
            source["name"], source["description"], release,
            last_checksum, source["codename"]
        )
        if updater.is_update_available():
            metadata = updater.get_metadata()
            # Update is available
            logger.info(
                f"{source['name']} - {release['name']} updated image found. "
                f"New release {metadata.version}"
            )
            # write changes to db
            database.write_or_update_catalog_entry(metadata)
            # mark changes to be processed later
            updated_releases.append(release["name"])
        else:
            logger.info(
                f"{source['name']} - {release['name']} No update found."
            )
    # return changes
    return updated_releases


def image_crawl_back_service(database: Database, source: dict) -> list:
    # Check if distros support crawlback or crawlback is implemented
    if source["name"] in ["AlmaLinux", "RockyLinux", "Fedora"]:
        logger.info(
            f"Only latest image available for {source['name']}."
        )
        if source["name"] == "Fedora":
            logger.info(
                "If you want to crawl Fedoras Major Versions, just add "
                "them by hand for consistent behaviour"
            )
        logger.info("Starting normal update")
        # just do normal update service and return its output
        return image_update_service(database, source)
    # Starting crawlback here
    updated_releases = []
    for release in source["releases"]:
        check_release(release["image"]["distro"], source["name"])
        # Set limit to default (3) if no limit is set
        release["limit"] = release["limit"] if "limit" in release else 3
        release_version_paths = get_crawl_back_release_paths(release)
        # Create Crawlback updater object
        for version_path in release_version_paths:
            # create crawler, build metadata and write to database
            crawler = ImageUpdateCrawler(
                source["name"], source["description"], release,
                source["codename"], version_path
            )
            database.write_or_update_catalog_entry(crawler.get_metadata())
            # add release name to updated_releases for later processing
            updated_releases.append(release["name"])
        return updated_releases


def check_release(image_distro: str, source_name: str) -> None:
    supported_releases = [
        "ubuntu", "debian", "AlmaLinux", "flatcar", "Fedora", "Rocky"
    ]
    if image_distro not in supported_releases:
        raise RuntimeError(
            f"Unsupported distribution {source_name}"
            " => Please check your images-sources.yaml. Skipping Releases."
        )


def get_crawl_back_release_paths(release_data: dict) -> list:
    """ Checks provided base url for release versions and returns links for
        amount of release_data['limit']
    """
    release_urls = []
    links = url_fetch_links(release_data["baseURL"])
    pattern = get_release_folder_pattern(
        release_data["image"],
        f"{release_data['image']['distro']} {release_data['image']['version']}"
    )
    while links:
        location = links.pop()
        if pattern.search(location):
            release_urls.append(path.join(release_data["baseURL"], location))
        if len(release_urls) == release_data["limit"]:
            # Stop search if enough releases found
            break
    return release_urls
