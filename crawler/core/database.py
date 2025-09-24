# database.py
import sqlite3
from loguru import logger
from os import path
from crawler.updater.metadata import Metadata, MetadataBase
from crawler.updater.update_check import ImageUpdateChecker


class Database:
    def __init__(self, database_path: str, init: bool = False) -> None:
        self.database_path = database_path
        self.init = init
        self._check_path()
        self.connection = self.connect()

    def _check_path(self) -> None:
        """ Check if a file exists on the target path. If its not the case and
            init=False then throw an exception
        """
        if (
                not self.init
                and not path.exists(self.database_path)
                or not path.isfile(self.database_path)
        ):
            raise FileNotFoundError(f"{self.database_path} not found!")

    def connect(self) -> sqlite3.Connection:
        """ Connect to db. Check if connection exists then restart it """
        if self._is_alive():
            self.disconnect()
        try:
            return sqlite3.connect(self.path)
        except sqlite3.OperationalError as error:
            raise RuntimeError(f"Error while connecting to DB\n{error}")

    def disconnect(self) -> None:
        """ Disconnect from db if connection exists and is open """
        if self._is_alive():
            self.connection.close()
            self.connection = None

    def execute_query(
        self, query: str, params: tuple = None,
        commit: bool = False, caller: str = None
    ) -> sqlite3.Cursor:
        """ sends a query and returns the cursor for data collection """
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            if commit:
                cursor.commit()
            return cursor
        except sqlite3.OperationalError as error:
            raise RuntimeError(
                f"Database execute ({caller}) failed\n{error}"
            )

    def _is_alive(self) -> bool:
        """ Service function to check if connection is alive """
        try:
            self.connection.cursor()
            return True
        except Exception:
            return False

    def _init_db(self) -> None:
        """ Create DB if it does not exist """
        if path.exists(self.database_path):
            raise FileExistsError(f"{self.database_path} already exists")
        init_file = path.join(
            path.dirname(path.abspath(__file__)),
            "lib/initialize-image-catalog.sql"
        )
        if not path.isfile(init_file):
            raise FileNotFoundError(f"Init file {init_file} not found")
        with open(init_file, "r") as fp:
            init_cmd = fp.read()
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
            "distribution_release, url, checksum "
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
        versions = []
        for row in data:
            metadata = MetadataBase()
            metadata.release_name = row[0]
            metadata.release_date = row[1]
            metadata.version = row[2]
            metadata.distribution_name = row[3]
            metadata.distribution_release = row[4]
            metadata.url = row[5]
            metadata.checksum = row[6]
            versions.append(metadata)
        return versions

    def get_last_entry(self, distribution: str, release: str) -> MetadataBase:
        """ shortcut for get_release_versions with limit 1 """
        versions = self.get_release_versions(distribution, release)
        if versions:
            return versions[0]
        else:
            return None


def read_version_from_catalog(
    connection: sqlite3.Connection, distribution: str,
    release: str, version: str
) -> dict:
    """ Search for the latest entry for given arguments """
    query = (
        "SELECT version, checksum, url, release_date "
        "FROM image_catalog "
        "WHERE distribution_name = ? "
        "AND distribution_release = ? "
        "AND version = ? "
        "ORDER BY id DESC LIMIT 1"
    )
    params = (distribution, release, version)
    try:
        database_cursor = connection.cursor()
        database_cursor.execute(query, params)
        # Just fetch the data since it is max one entry possible
        database_data = database_cursor.fetchone()
    except sqlite3.OperationalError as error:
        raise RuntimeError(
            f"DB OperationalError while fetching version from catalog\n{error}"
        )
    if not database_data:
        # There is no data to be used
        return None
    image = {
        "version": database_data[0],
        "checksum": database_data[1],
        "url": database_data[2],
        "release_date": database_data[3]
    }
    return image


def write_catalog_entry(
    connection: sqlite3.Connection, update: dict
) -> None:
    try:
        database_cursor = connection.cursor()
        database_cursor.execute(
            "INSERT INTO image_catalog "
            "(name, release_date, version, distribution_name, "
            "distribution_release, url, checksum) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                update["name"],
                update["release_date"],
                update["version"],
                update["distribution_name"],
                update["distribution_release"],
                update["url"],
                update["checksum"],
            ),
        )
        connection.commit()
    except sqlite3.OperationalError as error:
        raise RuntimeError(
            f"DB OperationalError while writing catalog entry\n{error}"
        )
    database_cursor.close()
    return None


def update_catalog_entry(
        connection: sqlite3.Connection, metadata: Metadata, checksum: str
) -> None:
    """ Update an existing entry """
    query = (
        "UPDATE image_catalog set url=?, checksum=?, release_date=?"
        "WHERE name=? AND version=?"
    )
    params = (
        metadata.url, checksum, metadata.release_date,
        metadata.release_name, metadata.version
    )
    try:
        database_cursor = connection.cursor()
        database_cursor.execute(query, params)
        connection.commit()
        database_cursor.close()
    except sqlite3.OperationalError as error:
        raise RuntimeError(
            f"DB OperationalError while updating catalog entry\n{error}"
        )
    return None


def write_or_update_catalog_entry(
    connection: sqlite3.Connection, update: ImageUpdateChecker
) -> None:
    existing_entry = read_version_from_catalog(
        connection,
        update.metadata.distribution_name,
        update.metadata.distribution_release,
        update.metadata.version
    )
    if existing_entry:
        logger.info(f"{update.metadata.release_name} updating version")
        update_catalog_entry(
            connection, update.metadata, update.current_checksum
        )
    else:
        write_catalog_entry(
            connection, update.metadata, update.current_checksum
        )
    return None


def read_release_from_catalog(
    connection: sqlite3.Connection, distribution: str,
    release: str, limit: int
) -> dict:
    if release == "all":
        call = "SELECT version,checksum,url,release_date,distribution_release \
            FROM (SELECT * FROM image_catalog \
            WHERE distribution_name = '{distribution}' \
            ORDER BY id DESC LIMIT {limit}) \
            ORDER BY ID"
    else:
        call = "SELECT version,checksum,url,release_date,distribution_release \
            FROM (SELECT * FROM image_catalog \
            WHERE distribution_name = '{distribution}' \
            AND distribution_release = '{release}' \
            ORDER BY id DESC LIMIT {limit}) \
            ORDER BY ID"
    try:
        database_cursor = connection.cursor()
        database_cursor.execute(call)
    except sqlite3.OperationalError as error:
        logger.error(
            f"DB OperationalError while reading release from catalog\n{error}"
        )
        raise SystemExit(1)

    image_catalog = {}
    image_catalog["versions"] = {}
    for image in database_cursor.fetchall():
        version = image[0]
        image_catalog["versions"][version] = {}
        image_catalog["versions"][version]["checksum"] = image[1]
        image_catalog["versions"][version]["url"] = image[2]
        image_catalog["versions"][version]["release_date"] = image[3]
        image_catalog["versions"][version]["distribution_release"] = image[4]
    return image_catalog
