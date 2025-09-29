# checksum.py
# Handle checksum and checking for checksum matching

import re
from os import path
from loguru import logger

from crawler.core.web import url_fetch_links, url_fetch_content
from crawler.updater.pattern import (
    get_checksum_search_pattern, get_checksum_pattern
)


class Checksum:
    def __init__(
        self, checksum: str, release_url: str, image_checksum_data: dict,
        image_data: dict
    ) -> None:
        self.last = checksum
        self.algorithm = image_checksum_data["algorithm"]
        self.filename = image_checksum_data["filename"]
        self.latest = f"{self.algorithm}:none"
        self.url = None
        self._main(release_url, image_checksum_data["filesearch"], image_data)

    def is_match(self) -> bool:
        """ Checks latest and last checksum and returns true if they match or
            latest checksum is None
        """
        if self.last == self.latest:
            logger.debug(f"Checksum matching! {self.latest}")
            return True
        if self.latest == f"{self.algorithm}:none":
            logger.warning("Checksum was not found")
            return True
        if self.latest is not None and self.last != self.latest:
            logger.debug(
                "Checksums do not match! "
                f"last: {self.last} <> latest: {self.latest}"
            )
            return False

    def _main(self, release_url: str, search: bool, image_data: dict) -> None:
        self._set_checksum_url(release_url, search)
        self._set_latest(image_data)

    def _set_latest(self, image_data: dict) -> None:
        """ """
        checksum_list = url_fetch_content(self.url)
        if not checksum_list:
            logger.warning(f"No content found for {self.url}")
            return None
        checksum_line_pattern = get_checksum_search_pattern(image_data)
        checksum_pattern = get_checksum_pattern(self.algorithm)
        logger.debug(f"line_pattern: {checksum_line_pattern}")
        logger.debug(f"checksum_patter: {checksum_pattern}")
        for line in checksum_list.splitlines():
            if not checksum_line_pattern.search(line):
                # Skip lines which not match image checksum pattern
                continue
            # search for the checksum in the line matching the image
            logger.debug(f"matching line: {line}")
            extract = checksum_pattern.search(line)
            if not extract:
                # Checksum not found. Print error. set checksum to None
                # will be later skipped in update check
                logger.error("Checksum in line matching image not found")
                return None
            self.latest = f"{self.algorithm}:{extract.group(1)}"
            # checksum found -> exit function
            break

    def _set_checksum_url(self, release_url: str, search: bool) -> None:
        """ builds checksum_url """
        self.url = path.join(release_url, self.filename)
        if search:
            self._set_checksum_by_search(release_url)
        logger.debug(f"checksum_url: {self.url}")

    def _set_checksum_by_search(self, release_url: str) -> None:
        """ Dynamically search for checksum file with provided parameters """
        all_files = url_fetch_links(release_url)
        pattern = re.compile(fr"{self.filename}")
        for file in all_files:
            if not pattern.search(file):
                continue
            self.filename = file
            self.url = path.join(release_url, file)
            return None
        raise RuntimeError(f"Could not find file with regex {self.filename}")
