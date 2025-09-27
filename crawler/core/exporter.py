# exporter.py

import os

from jinja2 import Template, TemplateAssertionError
from loguru import logger

from crawler.core.database import Database


class Exporter:
    def __init__(
        self, database: Database, image_source_catalog: dict,
        image_update_catalog: dict, repository: str, template_path: str
    ) -> None:
        # Database Object to use the sqlite3 database
        self.database = database
        # image-sources.yaml config file
        self.image_source_catalog = image_source_catalog
        # list of source["name"] which have updated versions
        self.image_update_catalog = image_update_catalog
        # repository to use
        self.repository = repository
        # path to templates which are needed to export images
        self.template_path = template_path
        # Check if repository exists otherwise create local folder to store
        # image information
        self._create_repository_folder()

    def _create_repository_folder(self) -> None:
        """ Create directory (once)
            only necessary when not created by git clone
        """
        if os.path.exists(self.repository):
            # if repository exists there is nothing to do
            return None
        try:
            os.makedirs(self.repository)
            logger.info(f"Created repository directory {self.repository}")
        except os.error as error:
            raise RuntimeError(
                f"Creating directory {self.repository} failed\n{error}"
            )

    def _get_template(self) -> Template:
        template_file_path = os.path.join(
            self.template_path, "generic.yml.j2"
        )
        if not os.path.exists(template_file_path):
            raise FileNotFoundError(f"Template {template_file_path} not found")
        try:
            with open(template_file_path, "r") as j2file:
                template = Template(j2file.read())
        except TemplateAssertionError as error:
            raise RuntimeError(
                f"Could not read Template file {template_file_path} with error"
                f": {error}"
            )
        return template

    def export_image_catalog(self) -> None:
        """ export just distributions with updates """
        for distribution in self.image_source_catalog:
            if distribution["name"] not in self.image_update_catalog:
                # If there is no update for this distribution (source['name'])
                # then skip it
                continue
            self.export_distribution(distribution["name"])

    def export_all_images(self) -> None:
        """ export all images. do not check if an update is available """
        for distribution in self.image_source_catalog:
            self.export_distribution(distribution["name"])

    def export_distribution(self, distribution_name: str) -> None:
        """ Creates yaml file for a specific distribution/image """
        logger.info(f"Start export of image catalog for {distribution_name}")
        for distribution in self.image_source_catalog:
            if distribution_name != distribution["name"]:
                continue
            distribution_data = distribution
            break
        template = self._get_template()
        distribution_export_catalog = {}
        latest_release_catalog = {}
        for release in distribution_data["releases"]:
            # Set limit of versions to fetch from database
            if "limit" in release:
                limit = release["limit"]
            else:
                # default is 3
                # NOTE: Maybe this value should be set in some config file
                limit = 3
            release_versions = self.database.get_release_versions(
                distribution_data["name"], release["name"], limit
            )
            if not release_versions:
                # if there is no version in db just fetch the next distro
                logger.info(
                    f"No data in db for {distribution['name']} "
                    f"({release['name']}) found!"
                )
                continue
            # save the fetched versions in the export catalog
            distribution_export_catalog[release["name"]] = release_versions
            if len(release_versions) > 1:
                latest_release_list = self.database.get_release_versions(
                    distribution_data["name"], release["name"], 1
                )
                latest_release_catalog[release["name"]] = \
                    latest_release_list[0]
            else:
                latest_release_catalog[release["name"]] = release_versions[0]

        distribution_release_string = \
            template.render(
                distribution=distribution_export_catalog,
                latest=latest_release_catalog,
                distribution_config=distribution_data
            )
        distribution_export_file = os.path.join(
            self.repository,
            f"{distribution_data['name'].lower().replace(' ', '_')}.yml"
        )
        with open(distribution_export_file, "w") as exportfile:
            exportfile.write(distribution_release_string)
