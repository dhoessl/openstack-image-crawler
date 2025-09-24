# database.py
import sqlite3
from loguru import logger
from os import path
from crawler.updater.metadata import Metadata, MetadataBase


class Database:
    def __init__(self, database_path: str, init: bool = False) -> None:
        self.database_path = database_path
        self.init = init
        self._check_path()
        self.connection = None
        if not self.init:
            self.connect()

    def _check_path(self) -> None:
        """ Check if a file exists on the target path. If its not the case and
            init=False then throw an exception
        """
        if (
                not self.init
                and not path.exists(self.database_path)
                or not path.isfile(self.database_path)
        ):
            raise FileNotFoundError(
                f"{self.database_path} not found! use '--init-db' to create "
                "a database"
            )

    def connect(self) -> None:
        """ Connect to db. Check if connection exists then restart it """
        if self.is_alive():
            self.disconnect()
        try:
            self.connection = sqlite3.connect(self.database_path)
        except sqlite3.OperationalError as error:
            raise RuntimeError(f"Error while connecting to DB\n{error}")

    def disconnect(self) -> None:
        """ Disconnect from db if connection exists and is open """
        if self.is_alive():
            self.connection.close()
            self.connection = None

    def execute_query(
        self, query: str, params: tuple = None,
        commit: bool = False, caller: str = None
    ) -> sqlite3.Cursor:
        """ sends a query and returns the cursor for data collection """

        try:
            if not self.is_alive():
                self.connect()
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            if commit:
                self.connection.commit()
            return cursor
        except sqlite3.OperationalError as error:
            raise RuntimeError(
                f"Database execute ({caller}) failed\n{error}"
            )

    def is_alive(self) -> bool:
        """ Service function to check if connection is alive """
        try:
            self.connection.cursor()
            return True
        except Exception:
            return False

    def init_db(self, program_dir) -> None:
        """ Create DB if it does not exist """
        if path.exists(self.database_path):
            raise FileExistsError(f"{self.database_path} already exists")
        init_file = path.join(
            program_dir,
            "lib/initialize-image-catalog.sql"
        )
        if not path.isfile(init_file):
            raise FileNotFoundError(f"Init file {init_file} not found")
        with open(init_file, "r") as fp:
            init_cmd = fp.read()
        self.connect()
        self.execute_query(init_cmd, caller="Init")
        logger.info("New database created at {self.database_path}")

    def get_last_checksum(
        self, distribution: str, release: str
    ) -> str:
        """ Fetches the last checksum from database for a given release """
        query = (
            "SELECT checksum FROM image_catalog"
            "WHERE distribution_name = ?"
            "AND distribution_release = ?"
            "ORDER BY id DESC LIMIT 1"
        )
        params = (distribution, release)
        cursor = self.execute_query(query, params, False, "Checksum")
        row = cursor.fetchone()
        cursor.close()
        if not row:
            logger.debug(
                "No previous Checksum found for {distribution} {release}"
            )
            return None
        else:
            return row[0]

    def get_release_versions(
        self, distribution: str, release: str, limit: int = 1
    ) -> list:
        query = (
            "SELECT name, release_date, version, distribution_name, "
            "distribution_release, url, checksum, checksum_url "
            "FROM image_catalog "
            "WHERE distribution_name = ? "
            "AND distribution_release = ? "
            "ORDER BY id DESC LIMIT ?"
        )
        params = (distribution, release, limit)
        cursor = self.execute_query(query, params, False, "Release Versions")
        data = cursor.fetchall()
        cursor.close()
        if not data:
            logger.info(
                "No release version found for {distribution} {release}"
            )
            return None
        metadata_list = []
        for row in data:
            metadata = MetadataBase()
            metadata.release_name = row[0]
            metadata.release_date = row[1]
            metadata.version = row[2]
            metadata.distribution_name = row[3]
            metadata.distribution_release = row[4]
            metadata.url = row[5]
            metadata.checksum = row[6]
            metadata.checksum_url = row[7]
            metadata_list.append(metadata)
        return metadata_list

    # previous was read_version_from_catalog
    def get_release_version_by_version(
        self, distribution: str, release: str, version: str, limit: int = 1
    ) -> list:
        """ Search for version, checksum, url and release date for a specific
            release version
        """
        query = (
            "SELECT version, checksum, url, release_date"
            "FROM image_catalog "
            "WHERE distribution_name = ? "
            "AND distribution_release = ? "
            "AND version = ? "
            "ORDER BY id DESC LIMIT ?"
        )
        params = (distribution, release, version, limit)
        cursor = self.execute_query(query, params, False, "Version Catalog")
        data = cursor.fetchall()
        cursor.close()
        if not data:
            logger.info(
                f"No dta was fetched for {distribution} {release} "
                f"version {version}"
            )
            return None
        metadata_list = []
        for row in data:
            metadata = MetadataBase()
            metadata.version = row[0]
            metadata.checksum = row[1]
            metadata.url = row[2]
            metadata.release_date = row[3]
            metadata_list.append(metadata)
        return metadata_list

    def write_catalog_entry(self, metadata: Metadata) -> None:
        """ Writes data from Metadata Object into db """
        query = (
            "INSERT INTO image_catalog "
            "(name, release_date, version, distribution_name, "
            "distribution_release, url, checksum, checksum_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        params = (
            metadata.release_name, metadata.release_date,
            metadata.distribution_name, metadata.distribution_release,
            metadata.url, metadata.checksum, metadata.checksum_url
        )
        self.execute_query(query, params, commit=True, caller="write entry")

    def update_catalog_entry(self, metadata: Metadata) -> None:
        """ Updates existing entry with data from Metadata object """
        query = (
            "UPDATE image_catalog set url=?, checksum=?, "
            "release_date=?, checksum_url=? "
            "WHERE name=? AND version=?"
        )
        params = (
            metadata.url, metadata.checksum, metadata.release_date,
            metadata.checksum_url, metadata.release_name, metadata.version
        )
        self.execute_query(query, params, commit=True, caller="update entry")

    def write_or_update_catalog_entry(self, metadata: Metadata) -> None:
        """ Checks if an entry exists and updates it or creates a new one """
        release_list = self.get_release_version_by_version(
            metadata.distribution_name, metadata.distribution_release,
            metadata.version
        )
        if release_list and len(release_list) > 0:
            logger.info(f"{metadata.release_name} version update")
            self.update_catalog_entry(metadata)
        else:
            logger.debug(f"{metadata.release_name} create entry")
            self.write_catalog_entry(metadata)

    def update(self) -> None:
        """ Checks if current db is up to date and if not upgrades it """
        table_info_cursor = self.execute_query(
            "PRAGMA table_info(image_catalog)", caller="Updater"
        )
        table_info = table_info_cursor.fetchall()
        for row in table_info:
            if row[1] == "checksum_url":
                return None
        logger.warning(
            "Updating Database Table. Adding checksum_url column"
        )
        self.execute_query(
            "ALTER TABLE image_catalog ADD checksum_url text",
            commit=True, caller="checksum_url upgrade"
        )
        logger.info("Table update finished")
        # TODO: pull all releases and add checksum_url
