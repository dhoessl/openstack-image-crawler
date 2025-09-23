import sys
import sqlite3

from loguru import logger
from pathlib import Path


def database_connect(
    database_path: str, init: bool = False
) -> sqlite3.Connection:
    path = Path(database_path)
    if not path.is_file():
        logger.error("Database at {path} not found")
        return None
    try:
        connection = sqlite3.connect(path)
    except sqlite3.OperationalError as error:
        logger.error(f"Databse OperationalError\n{error}")
        return None
    return connection


def database_disconnect(connection: sqlite3.Connection) -> None:
    connection.close()


def database_initialize(database_path: str, prog_dirname: str) -> None:
    path = Path(database_path)
    if path.is_file():
        logger.warning(f"database {path} already exists. Refusing action.")
        return None
    create_statement_file_path = Path(
        f"{prog_dirname}/lib/initialize-image-catalog.sql"
    )
    if not create_statement_file_path.is_file():
        logger.error("Template initialize-image-catalog.sql not found")
        raise SystemExit(1)
    db_init_file = open(create_statement_file_path)
    create_statement = db_init_file.read()
    db_init_file.close()
    connection = database_connect(path, init=True)
    try:
        database_cursor = connection.cursor()
        database_cursor.execute(create_statement)
    except Exception as error:
        logger.error(f"Create table failed!\n{error}")
    database_disconnect(connection)
    logger.info(f"New database created under {path}")


def db_get_last_checksum(
    connection: sqlite3.Connection, distribution: str, release: str
) -> str:
    if release == "all":
        call = f"SELECT checksum FROM image_catalog \
            WHERE distribution_name = '{distribution}' \
            ORDER BY id DESC LIMIT 1"
    else:
        call = f"SELECT checksum FROM image_catalog \
            WHERE distribution_name = '{distribution}' \
            AND distribution_release = '{release}' \
            ORDER BY id DESC LIMIT 1"
    try:
        database_cursor = connection.cursor()
        database_cursor.execute(call)
    except sqlite3.OperationalError as error:
        logger.error(
            f"Database OperationalError while fetching checksum\n{error}"
        )
        raise SystemExit(1)

    row = database_cursor.fetchone()
    if row is None:
        logger.debug("no previous entries found")
        last_checksum = "sha256:none"
    else:
        last_checksum = row[0]

    database_cursor.close()
    return last_checksum


def db_get_release_versions(
        connection: sqlite3.Connection, distribution: str,
        release: str, limit: int
) -> dict:
    logger.debug(
        f"distribution: {distribution} release: {release} limit: {limit}"
    )
    if release == "all":
        call = "SELECT name, release_date, version, distribution_name, \
            distribution_release, url, checksum FROM image_catalog \
            WHERE distribution_name = '{distribution}' \
            ORDER BY id DESC LIMIT {limit}"
    else:
        call = "SELECT name, release_date, version, distribution_name, \
            distribution_release, url, checksum FROM image_catalog \
            WHERE distribution_name = '{distribution}' \
            AND distribution_release = '{release}' \
            ORDER BY id DESC LIMIT {limit}"
    try:
        database_cursor = connection.cursor()
        database_cursor.execute(call)
    except sqlite3.OperationalError as error:
        logger.error(
            f"DB OperationalError while fetching release versions\n{error}"
        )
        sys.exit(1)
    row = database_cursor.fetchone()

    if row is not None:
        last_entry = {}
        last_entry["name"] = row[0]
        last_entry["release_date"] = row[1]
        last_entry["version"] = row[2]
        last_entry["distribution_name"] = row[3]
        last_entry["distribution_version"] = row[4]
        last_entry["url"] = row[5]
        last_entry["checksum"] = row[6]

        database_cursor.close()
        return last_entry
    else:
        # or empty dict?
        return None


def db_get_last_entry(
    connection: sqlite3.Connection, distribution: str, release: str
) -> dict:
    return db_get_release_versions(connection, distribution, release, 1)


def read_version_from_catalog(
    connection: sqlite3.Connection, distribution: str,
    release: str, version: str
) -> dict:
    if release == "all":
        call = "SELECT version,checksum,url,release_date \
            FROM (SELECT * FROM image_catalog \
            WHERE distribution_name = '{distribution}' \
            AND version ='{version}' \
            ORDER BY id DESC LIMIT 1) \
            ORDER BY ID"
    else:
        call = "SELECT version,checksum,url,release_date \
            FROM (SELECT * FROM image_catalog \
            WHERE distribution_name = '{distribution}' \
            AND distribution_release = '{release}' \
            AND version ='{version}' \
            ORDER BY id DESC LIMIT 1) \
            ORDER BY ID"
    try:
        database_cursor = connection.cursor()
        database_cursor.execute(call)
    except sqlite3.OperationalError as error:
        logger.error(
            f"DB OperationalError while fetching version from catalog\n{error}"
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

    return image_catalog


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
        logger.error(
            f"DB OperationalError while writing catalog entry\n{error}"
        )
        raise SystemExit(1)
    database_cursor.close()
    return None


def update_catalog_entry(
    connection: sqlite3.Connection, update: dict
) -> None:
    try:
        database_cursor = connection.cursor()
        database_cursor.execute(
            "UPDATE image_catalog set url=?, checksum=? "
            "WHERE name=? AND version=?",
            (
                update["url"],
                update["checksum"],
                update["name"],
                update["version"]
            ),
        )
        connection.commit()
    except sqlite3.OperationalError as error:
        logger.error(
            f"DB OperationalError while updating catalog entry\n{error}"
        )
        raise SystemExit(1)
    database_cursor.close()
    return None


def write_or_update_catalog_entry(
    connection: sqlite3.Connection, update: dict
) -> None:
    existing_entry = read_version_from_catalog(
        connection,
        update["distribution_name"],
        update["distribution_release"],
        update["version"]
    )
    if update["version"] in existing_entry["versions"]:
        if "Fedora" in update["name"]:
            logger.info(f"Updating release {update['distribution_release']}")
        else:
            logger.info("Updating version {update['version']}")
        return update_catalog_entry(connection, update)
    else:
        return write_catalog_entry(connection, update)


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
