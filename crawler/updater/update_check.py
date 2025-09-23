# Check for updates on supported releases

import re
from os import path
from loguru import logger
from crawler.web.generic import url_fetch_links, url_fetch_content
from crawler.updater.metadata import Metadata
from crawler.updater.pattern import (
    get_checksum_search_pattern,
    get_checksum_pattern
)


class ImageUpdateChecker:
    """ Class to check for updates and create an object for metadata
        information. Requires the one release dict from releases list.
    """
    def __init__(
        self, source_name: str, release: dict, last_checksum: str
    ) -> None:
        self.release = release
        self.last_checksum = last_checksum
        self.distribution_name = source_name
        self.current_checksum = None
        self.release_url = None
        self.update_available = False
        self.metadata = None
        self._setup_vars()

    def check_update(self) -> bool:
        """ Checks if checksums non matching and updating metadata if needed.
            sets self.update_available to True if an update is possible.
            returns bool coresponding to self.update_available
        """
        if self.current_checksum == self.last_checksum:
            logger.debug("checksum matches -> no update")
            return self.update_available
        if self.current_checksum is None:
            logger.warning("Checksum is None -> no update")
            return self.update_available
        logger.debug(
            "Checksum dont match => Fetching new image data! "
            f"{self.last_checksum} <> {self.current_checksum}"
        )
        image_metadata = Metadata(
            self.release_url, self.release["baseURL"],
            self.release["image"], self.distribution_name,
            self.release["name"]
        )
        image_metadata.build_metadata()
        if not image_metadata.url:
            logger.warning(f"got no metadata for {self.release['imagename']}")
            return self.update_available
        logger.debug(f"{self.release['image']['distro']} - metadata found")
        self.metadata = image_metadata
        self.update_available = True
        return self.update_available

    def _setup_vars(self) -> None:
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
        if "latest" in self.release and self.release["latest"]:
            search_pattern = fr"{self.release['name']}"
            links = url_fetch_links(self.release["baseURL"])
            while links:
                link = links.pop()
                extract = search_pattern.search(link.get("href"))
                if extract:
                    self.release_url = path.join(
                        self.release["baseURL"],
                        link.get("href"),
                        self.release["releasepath"]
                    )
                    self.release["name"] == extract.group(1)
                    break
            logger.warning(
                f"No relese_url for {self.release['image']['distro']} found"
            )
            return None
        logger.debug(f"release_url: {self.release_url}")
        self.current_checksum = self.release["image"]["algorithm"] + ":" \
            + self._get_checksum()
        logger.debug("current checksum: {self.current_checksum}")

    def _get_checksum(self) -> str:
        """ creates checksum_url from provided information and searches it for
            hash of provided image information.
            search pattern is build _get_checksum_search_pattern and can be
            filled with further patterns if required.
        """
        checksum_url = path.join(
            self.release_url,
            self.release["checksum"]["filename"]
        )
        if (
            "filesearch" in self.release["checksum"]
            and self.release["checksum"]["filesearch"]
        ):
            checksum_url = self._get_dynamic_checksum_url()
        logger.debug(f"checksum_url: {checksum_url}")
        checksum_list = url_fetch_content(checksum_url)
        if checksum_list is None:
            logger.warning(f"No content found in {checksum_url}")
            return None
        checksum_line_pattern = get_checksum_search_pattern(
            self.release["image"], self.distribution_name
        )
        checksum_pattern = get_checksum_pattern(
            self.release["checksum"]["algorithm"]
        )
        for line in checksum_list.splitlines():
            if not checksum_line_pattern.search(line):
                # Skip line if its not matching the search pattern
                continue
            # if line matches extract checksum
            extract = checksum_pattern.search(line)
            if not extract:
                logger.warning("checksum found but could not extract")
                return None
            return extract.group(1)  # group which is the checksum
        return None

    def _get_dynamic_checksum_url(self) -> str:
        """ If the checksum file changes its name this is a way to do a dynamic
            search for a file in the release_url folder.
            To use this set release['checksum']['filesearch'] to true
            and release['checksum']['filename'] to a regex string which
            finds the file
        """
        all_files = url_fetch_links(self.release_url)
        pattern = re.compile(fr"{self.release['checksum']['filename']}")
        for file in all_files:
            if pattern.search(file):
                return path.join(self.release_url, file)
