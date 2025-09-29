# Check for updates on supported releases

from os import path
from loguru import logger

from crawler.core.web import url_fetch_links
from crawler.updater.metadata import Metadata
from crawler.updater.checksum import Checksum
from crawler.updater.pattern import get_latest_distribution_pattern


class ImageUpdateBase:
    def __init__(
        self, source_name: str, image_description: str | list,
        release: dict
    ) -> None:
        self.release = release
        self.distribution_name = source_name
        self.description_base = image_description
        self.release_url = None  # url check for image file
        self.checksum = None  # Checksum Object
        self.metadata = None  # Metadata Object
        self._sanitize()

    def _sanitize(self) -> None:
        """ Cleans up variables and sets defaults """
        # Set filesearch to default: False
        if "filesearch" not in self.release["checksum"]:
            self.release["checksum"]["filesearch"] = False

    def is_update_available(self) -> bool:
        """ Checks Checksum Object. If Checksum Object indicates that checksum
            are out of sync than an update is possible.
        """
        if self.checksum.is_match():
            logger.debug("No Update!")
            return False
        else:
            logger.debug("Update Possible")
            return True

    def get_metadata(self, crawling: bool = False) -> Metadata:
        """ builds metadata Object from Metadata class if not build before
            and returns it
        """
        if type(self.metadata) is not Metadata:
            logger.debug("Creating Metadata since it was not created before")
            self.metadata = Metadata(
                self.release, self.release_url, self.distribution_name,
                self.checksum, self.description_base
            )
            self.metadata.build_metadata(crawling)
        return self.metadata


class ImageUpdateChecker(ImageUpdateBase):
    """ Class to check for updates and create an object for metadata
        information. Requires the one release dict from releases list.
    """
    def __init__(
        self, source_name: str, image_description: str | list,
        release: dict, last_checksum: str
    ) -> None:
        super().__init__(source_name, image_description, release)
        self._setup_vars(last_checksum)

    def _setup_vars(self, last_checksum: str) -> None:
        """ Setup some basic vars needed for metadata fetching.
            this function is created to not clutter __init__.
        """
        self.release_url = path.join(
            self.release["baseURL"],
            self.release["releasepath"]
        )
        # If you set releases[...]['latest'] to True and provide an explicit
        # search pattern with one capture group in releases[...]['name']
        # this part searches for latest release on the baseURL
        # releases[...]['name'] will be set to output of the capture group
        if (
            "latest" in self.release["image"]
            and self.release["image"]["latest"]
        ):
            search_pattern = get_latest_distribution_pattern(
                self.release["latest_regex"]
            )
            logger.debug(f"search_pattern: {search_pattern}")
            links = url_fetch_links(self.release["baseURL"])
            while links:
                link = links.pop()
                extract = search_pattern.search(link)
                if extract:
                    logger.debug(f"link found: {link} with {extract}")
                    self.release_url = path.join(
                        self.release["baseURL"],
                        link,
                        self.release["releasepath"]
                    )
                    self.release["name"] == extract.group(1)
                    break
            if not extract:
                logger.warning(
                    f"No relese_url for {self.release['image']['distro']} found"
                )
                return None
        logger.debug(f"release_url: {self.release_url}")
        self.checksum = Checksum(
            last_checksum, self.release_url, self.release["checksum"],
            self.release["image"]
        )
        logger.debug(f"current checksum: {self.checksum.latest}")


class ImageUpdateCrawler(ImageUpdateBase):
    def __init__(
        self, source_name: str, image_description: str | list,
        release: dict, release_path: str
    ) -> None:
        super().__init__(source_name, image_description, release)
        self._setup_vars(release_path)

    def _setup_vars(self, release_path: str) -> None:
        self.release_url = release_path
        logger.debug(f"release_url: {self.release_url}")
        # Set default filesearch to False
        old_checksum = f"{self.release['checksum']['algorithm']}:none"
        self.checksum = Checksum(
            old_checksum, self.release_url, self.release["checksum"],
            self.release["image"]
        )
        logger.debug(f"current checksum: {self.checksum.latest}")
