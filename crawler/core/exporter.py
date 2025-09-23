from jinja2 import Template
import os

from crawler.core.database import read_release_from_catalog
from crawler.web.generic import format_url_part
from loguru import logger
from sqlite3 import Connection


def create_local_repository(repository) -> None:
    """ Create directory (once)
        only necessary when not created by git clone
    """
    if not os.path.exists(repository):
        try:
            logger.info(
                f"Creating repository directory {repository}"
            )
            os.makedirs(repository)
        except os.error as error:
            logger.error(
                f"Creating directory {repository} failed with {error}"
            )
            raise SystemExit(1)


def export_image_catalog_helper(
    connection: Connection, local_repository: str,
    template_path: str, source: dict
) -> None:
    distribution = source["name"]
    logger.info(f"Exporting image catalog for {distribution}")

    catalog_export = ""

    image_template_filename = os.path.join(
        template_path, f"{distribution.lower().replace(' ', '_')}.yml.j2",
    )
    image_template_file = open(image_template_filename, "r")
    image_template = Template(image_template_file.read())
    image_template_file.close()

    for release in source["releases"]:
        if "limit" in release:
            limit = release["limit"]
        else:
            limit = 3

        release_catalog = read_release_from_catalog(
            connection, distribution, release["name"], limit
        )
        if release_catalog["versions"]:
            release_catalog["name"] = distribution
            release_catalog["os_distro"] = distribution.lower()
            release_catalog["os_version"] = release["name"]
            release_catalog["codename"] = release["codename"]

            logger.debug(
                f"Rendering template for {release_catalog['name']} "
                f"{release_catalog['os_version']}"
            )

            catalog_export = (
                catalog_export
                + image_template.render(
                    catalog=release_catalog, metadata=release
                )
                + "\n"
            )
        else:
            logger.warning(
                f"got no catalog entries for {distribution} {release['name']}"
            )

    if len(release_catalog) > 0:
        header_file = open(template_path + "/header.yml")
        catalog_header = header_file.read()
        header_file.close()

        catalog_export = catalog_header + catalog_export

        image_catalog_export_filename = os.path.join(
            local_repository,
            f"{distribution.lower().replace(' ', '_')}.yml"
        )
        image_catalog_export_file = open(
            image_catalog_export_filename, "w"
        )
        image_catalog_export_file.write(catalog_export)
        image_catalog_export_file.close()
    else:
        logger.debug(f"nothing to export for {distribution}")


def export_image_catalog(
    connection: Connection, sources_catalog: dict,
    updated_sources: dict, local_repository: str, template_path: str
) -> None:
    # "smart" export - only releases with updates will be written
    create_local_repository(local_repository)
    for source in sources_catalog["sources"]:
        if source["name"] in updated_sources:
            export_image_catalog_helper(
                connection,
                local_repository,
                template_path,
                source
            )


def export_image_catalog_all(
    connection: Connection, sources_catalog: dict,
    local_repository: str, template_path: str
):
    # export all releases - used with --export-only
    create_local_repository(local_repository)

    for source in sources_catalog["sources"]:
        export_image_catalog_helper(
            connection,
            local_repository,
            template_path,
            source
        )
