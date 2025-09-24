# service.py

# providing core functionality for the crawler in updating and crawling images
from loguru import logger

from crawler.core.database import Database
# from crawler.updater.ubuntu import ubuntu_update_check, ubuntu_crawl_release
# from crawler.updater.debian import debian_update_check, debian_crawl_release
# from crawler.updater.alma import alma_update_check
# from crawler.updater.flatcar import flatcar_update_check
# from crawler.updater.fedora import fedora_update_check, fedora_crawl_release
# from crawler.updater.rocky import rocky_update_check

from crawler.updater.update_check import ImageUpdateChecker


# def image_crawl_back_service(connection, source):
#     for release in source["releases"]:
#         catalog_entry_list = []
#         if "ubuntu" in release["imagename"]:
#             catalog_entry_list = ubuntu_crawl_release(release)
#         elif "debian" in release["imagename"]:
#             catalog_entry_list = debian_crawl_release(release)
#         elif "Fedora" in release["imagename"]:
#             catalog_entry_list = fedora_crawl_release(release)
#         else:
#             # fall back for distributions with only latest release online
#             # or yet unsupported distribution
#             last_checksum = db_get_last_checksum(
#                     connection, source["name"], release["name"]
#                 )
#             if "Alma" in release["imagename"]:
#                 logger.warning("Only the last Alma Linux release is online" +
#                                " - falling back to normal update service")
#                 catalog_entry = alma_update_check(release, last_checksum)
#                 if catalog_entry:
#                     catalog_entry_list.append(catalog_entry)
#             elif "flatcar" in release["imagename"]:
#                 logger.warning("Crawling of previous Flatcat Linux versions" +
#                                " not yet supported - falling back to normal" +
#                                " update service")
#                 catalog_entry = flatcar_update_check(release, last_checksum)
#                 if catalog_entry:
#                     catalog_entry_list.append(catalog_entry)
#             # elif "Fedora" in release["imagename"]:
#             #     logger.warning("Crawling of previous Fedora Linux versions" +
#             #                    " not yet supported - falling back to normal" +
#             #                    " update service")
#             #     catalog_entry = fedora_update_check(release, last_checksum)
#             #     if catalog_entry:
#             #         catalog_entry_list.append(catalog_entry)
#             elif "Rocky" in release["imagename"]:
#                 logger.warning("Crawling of previous Rocky Linux version" +
#                                " not yet supported - falling back to normal" +
#                                " update service")
#                 catalog_entry = rocky_update_check(release, last_checksum)
#                 if catalog_entry:
#                     catalog_entry_list.append(catalog_entry)
#             else:
#                 # not yet supported distribution
#                 logger.warning("Crawling versions of distribution " + source["name"] +
#                             " not (yet) supported")
#
#         if catalog_entry_list:
#             logger.info("Versions found for " + source["name"] + " " + release["name"])
#             for catalog_entry in catalog_entry_list:
#                 # catalog_entry anreichern mit _allen_ Daten für die DB
#                 catalog_entry["distribution_name"] = source["name"]
#                 if "Fedora" in release["imagename"]:
#                     logger.info("Version found " + catalog_entry["release_id"])
#                     catalog_entry["name"] = source["name"] + " " + catalog_entry["release_id"]
#                     catalog_entry["distribution_release"] = catalog_entry["release_id"]
#                 else:
#                     logger.info("Version found " + catalog_entry["version"])
#                     catalog_entry["name"] = source["name"] + " " + release["name"]
#                     catalog_entry["distribution_release"] = release["name"]
#                 catalog_entry["release"] = release["name"]
#
#                 write_or_update_catalog_entry(connection, catalog_entry)
#                 # Commit message or just "initial commit"
#                 # catalog_entry_list.append(release["name"])


def image_update_service(database: Database, source: dict) -> dict:
    updated_releases = []
    for release in source["releases"]:
        # Check if release is supported. If its no supported exception will be
        # raised.
        check_release(release["image"]["distro"], source["name"])
        last_checksum = database.get_last_checksum(
            source["name"], release["name"]
        )
        if not last_checksum:
            # Set checksum to none if there is no checksum for the release
            last_checksum = f"{release['checksum']['algorithm']}:none"
        logger.debug("last_checksum:" + last_checksum)
        # create Updater Object and run an update check
        updater = ImageUpdateChecker(source["name"], release, last_checksum)
        updater.check_update()
        if updater.update_available:
            # Update is available
            logger.info(
                f"{source['name']} - {release['name']} updated image found. "
                f"New release {updater.update['version']}"
            )
            # write changes to db
            database.write_or_update_catalog_entry(updater.metadata)
            # mark changes to be processed later
            updated_releases.append(release["name"])
        else:
            logger.info(
                f"{source['name']} - {release['name']} No update found."
            )
    # return changes
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
