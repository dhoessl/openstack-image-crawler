# metadata.py
# Class Metadata to collect and store image metadata information

import re

from loguru import logger
from datetime import datetime
from os import path

from crawler.web.generic import url_get_last_modified, url_fetch_links
from crawler.updater.checksum import Checksum
from crawler.updater.pattern import (
    get_filename_pattern, get_release_folder_pattern
)


class MetadataBase:
    """ provides core vars for metadata without further processing """
    def __init__(self) -> None:
        self.base_url = None  # url pointing to release base folder
        self.release_url = None  # url pointing to image base folder
        self.distribution_release = None  # release["name"]
        self.distribution_name = None  # source["name"]
        self.release_name = None  # f"{distribution_name} {image_name}"
        self.checksum = None  # Checksum Object
        self.url = None  # url pointing to release download
        self.major = None  # major release version
        self.minor = None  # minor release version
        self.patch = None  # patch release version
        self.release_date = None  # release date in %Y-%m-%d
        self.release_date_suffix = None  # release date suffix
        self.version = None  # release_date in %Y%m%d
        self.arch = None  # release['arch']
        self.description = None  # Some sort of image description

    def _format_release_date(self) -> None:
        """ formate the release date into %Y-%m-%d """
        self.release_date = datetime\
            .strptime(self.release_date, "%Y%m%d")\
            .strftime("%Y-%m-%d")

    def _get_version_from_date(self, filedate) -> str:
        """ format %Y-%m-%d date to %Y%m%d version format """
        return datetime.strptime(filedate, "%Y-%m-%d").strftime("%Y%m%d")


class Metadata(MetadataBase):
    """ provides vars for all available metadata.
        data will be fetched from provided information
    """
    def __init__(
        self, release: dict, release_url: str, distribution_name: str,
        checksum: Checksum, description: str | list, codename: str
    ) -> None:
        """ create all possible metadata vars """
        super.__init__()
        self.release_url = release_url
        self.base_url = release["baseURL"]
        self.image_data = release["image"]
        self.distribution_release = release["name"]
        self.distribution_name = distribution_name  # source["name"]
        self.release_name = f"{distribution_name} {release['image']['name']}"
        self.checksum = checksum  # Checksum Object holding all checksum data
        self.arch = release["image"]["arch"]
        self.description = description
        self.codename = codename
        self.log_prefix = \
            f"{self.distribution_name}({self.image_data['version']})"
        self.filename_pattern = get_filename_pattern(
            self.image_data, self.log_prefix
        )  # function from crawler/updater/pattern.py

    def build_metadata(self) -> bool:
        """ fetch image name and build metadata from _self_ values and image
            name
        """
        # call specific function for extraction
        if self.image_data["distro"] in ["AlmaLinux", "Rocky", "Fedora"]:
            extract = self._get_simple_extract()
        elif self.image_data["distro"] in ["ubuntu", "debian", "flatcar"]:
            extract = self._get_dated_extract()
        # Check if extract holds data
        if not extract:
            # extraction did not work logger should already printed info
            return False
        # set metadata
        self._set_metadata_from_extract(extract)
        # When metadata was fetched we can build description
        # since it might depend on image versions
        self._convert_description()
        return True

    def _convert_description(self) -> None:
        """ convert release["description"] list or string into metadata var """
        if type(self.description) is str:
            # description is in the correct format and does not need to be
            # converted
            return None
        description = ""
        supported_vars = ["CODENAME", "MAJOR", "MINOR"]
        for element in self.description:
            if element not in supported_vars:
                # Add the string to description if the element does not
                # include a supported variable.
                description += element
                continue
            # If there are more vars required add them here
            if element == "CODENAME":
                description += self.codename
            elif element == "MAJOR":
                description += str(self.major)
            elif element == "MINOR":
                description += str(self.minor)
        self.description = description

    def _get_dated_extract(self) -> re.Match:
        """ Search for the latest dated release folder by a given pattern.
            Change self.release_url to that folder and return output of
            _get_simple_extract(). This makes sure to always get the latest
            release folder since latest dated release image is not included in
            latest release folder.
            The release folder page will be traversed from the back and every
            provided link is matched against the given pattern.
        """
        latest_release_folder = self._get_latest_release_folder(self.base_url)
        if not latest_release_folder:
            logger.warning(f"{self.log_prefix} => no release folder found!")
            return None
        self.release_url = path.join(self.base_url, latest_release_folder)
        return self._get_simple_extract()

    def _get_simple_extract(self) -> re.Match:
        """ Fetch image name and return the grouped extract """
        links = url_fetch_links(self.release_url)
        if links is None:
            logger.warning(f"{self.log_prefix} => no image found!")
            return None
        logger.debug(f"filename_pattern: {self.filename_pattern.pattern}")
        for link in links:
            if self.filename_pattern.search(link):
                logger.debug(f"pattern matched for {link}")
                self.url = path.join(self.release_url, link)
                return self.filename_pattern.search(link)
        logger.warning(
            "No links found for filename pattern "
            f"{self.filename_pattern.pattern}"
        )
        return None

    def _set_metadata_from_extract(self, extract: re.Match) -> None:
        """ extract metadata from image filename """
        if self.image_data["distro"] in ["AlmaLinux", "Rocky"]:
            self.major = extract.group(1)
            self.minor = extract.group(3)
            if "." in extract.group(4):
                self.release_date = extract.group(6)
                self.release_date_suffix = extract.group(7)
            else:
                self.release_date = extract.group(5)
            self.version = self.release_date
            self._format_release_date()
        elif self.image_data["distro"] == "debian":
            self.major = extract.group(1)
            self.release_date = extract.group(3)
            self.version = extract.group(2)
            self._format_release_date()
        elif self.image_data["distro"] == "ubuntu":
            self.version = self.url.split("/")[-2].split("-")[1]
            self.release_date = re.match(
                r"^(\d{8})\.(\d+)?$", self.version
            ).group(1)
            self.release_date_suffix = re.match(
                r"^(\d{8})\.(\d+)?$", self.version
            ).group(2)
            self._format_release_date()
        elif self.image_data["distro"] == "flatcar":
            self.release_date = url_get_last_modified(self.url)
            self.version = self._get_version_from_date(self.release_date)
            self.major = self.version.split(".")[0]
            self.minor = self.version.split(".")[1]
            self.patch = self.version.split(".")[2]
        elif self.image_data["distro"] == "Fedora":
            self.release_date = url_get_last_modified(self.url)
            self.version = self._get_version_from_date(self.release_date)
            self.major = extract.group(2)
            self.minor = extract.group(3)
            self.patch = extract.group(4)
        else:
            raise RuntimeError(
                f"{self.log_prefix} extracting is not implemented!"
            )

    def _get_latest_release_folder(self, url: str) -> str:
        """ find a folder depending on a given pattern and return the locaiton
        """
        # fetch all links from given url
        links = url_fetch_links(url)
        pattern = get_release_folder_pattern(self.image_data, self.log_prefix)
        # loop every link on given page
        # and check if its a match for a release foldern described by
        # the pattern
        while links:
            link = links.pop()  # get last link
            location = link.get("href")  # get target location
            if pattern.search(location):
                # if location and pattern matches return the location
                return location
        # If no link maches the pattern return nothing
        return None
