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
                and (
                    not path.exists(self.database_path)
                    or not path.isfile(self.database_path)
                )
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
                logger.debug(f"query: {query}")
                logger.debug(f"params: {params}")
                cursor.execute(query, params)
            else:
                logger.debug(f"query: {query}")
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
        logger.info(f"New database created at {self.database_path}")

    def get_last_checksum(
        self, distribution: str, release: str, limit: int = 1
    ) -> str | list:
        """ Fetches the last checksum from database for a given release """
        query = (
            "SELECT checksum FROM image_catalog "
            "WHERE distribution_name = ? "
            "AND distribution_release = ? "
            "ORDER BY id DESC LIMIT ?"
        )
        params = (distribution, release, limit)
        cursor = self.execute_query(query, params, False, "Checksum")
        rows = cursor.fetchall()
        cursor.close()
        if not rows:
            logger.debug(
                f"No previous Checksum found for {distribution} {release}"
            )
            return None
        elif len(rows) == 1:
            return rows[0][0]
        else:
            checksum_list = []
            for row in rows:
                checksum_list.append(row[0])
            return checksum_list

    def get_last_checksum_by_version(
        self, distribution: str, release: str, limit: int = 1
    ) -> list:
        query = (
            "SELECT checksum, version FROM image_catalog "
            "WHERE distribution_name = ? "
            "AND distribution_release = ? "
            "ORDER BY id DESC LIMIT ?"
        )
        params = (distribution, release, limit)
        cursor = self.execute_query(query, params, False, "Checksum versions")
        rows = cursor.fetchall()
        cursor.close()
        checksum_list = []
        if not rows:
            logger.debug(
                "No previous Checksums found for {distribution} {release}"
            )
            return checksum_list
        for row in rows:
            checksum_list.append({
                "checksum": row[0],
                "version": row[1]
            })
        return checksum_list

    def get_release_versions(
        self, distribution: str, release: str, limit: int = 1
    ) -> list:
        query = (
            "SELECT name, release_date, version, distribution_name, "
            "distribution_release, url, checksum, checksum_url, arch, "
            "description "
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
                f"No release version found for {distribution} {release}"
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
            metadata.arch = row[8]
            metadata.description = row[9]
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
            "SELECT version, checksum, url, release_date "
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
                f"No data was fetched for {distribution} {release} "
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
            "distribution_release, url, checksum, checksum_url, arch, "
            "description) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        params = (
            metadata.release_name, metadata.release_date, metadata.version,
            metadata.distribution_name, metadata.distribution_release,
            metadata.url, metadata.checksum.latest,
            metadata.checksum.url, metadata.arch, metadata.description
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
            metadata.url, metadata.checksum.latest, metadata.release_date,
            metadata.checksum.url, metadata.release_name, metadata.version
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
        columns_to_create = ["checksum_url", "arch", "description"]
        for row in table_info:
            if row[1] in columns_to_create:
                columns_to_create.pop(columns_to_create.index(row[1]))
        if not columns_to_create:
            # Exist if all new columns exist
            return None
        logger.warning(
            "Updating Database Table. Adding missing columns "
            f"({', '.join(columns_to_create)})"
        )
        for column in columns_to_create:
            # sqlite3 does not allow subsitution for column names
            # this is why f-string is used here.
            # This should be no issue since there cant be code injected at
            # this point and just pre-defined column names are created
            query = f"ALTER TABLE image_catalog ADD COLUMN {column} text"
            self.execute_query(query, commit=True, caller="Column Upgrade")
        logger.info("Table update finished")
        # TODO: pull all releases and fill missing data
