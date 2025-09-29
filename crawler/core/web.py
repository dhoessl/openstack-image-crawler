import requests
import validators

from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
from loguru import logger
from time import sleep


def url_do_request(url: str) -> requests.models.Response:
    if not validators.url(url):
        logger.error(f"{url} is not a valid URL")
        return None
    for attempt in range(3):
        try:
            request = requests.get(url, allow_redirects=True, timeout=5)
        except requests.exceptions.HTTPError as errh:
            raise RuntimeError(f"HTTP error: {repr(errh)}")
            return None
        except requests.exceptions.ConnectionError as errc:
            logger.error(f"could not connect to the API: {repr(errc)}")
            sleep(2)
        except requests.exceptions.Timeout as errt:
            logger.error(f"timeout while connecting: {repr(errt)}")
            sleep(2)
        except requests.exceptions.RequestException as err:
            raise RuntimeError(f"unknown error: {repr(err)}")
    if request.status_code == 404:
        logger.warning(f"Page not found. Error 404 => {url}")
        return None
    if not request:
        raise RuntimeError(f"Error while fetching {url}")
    return request


def url_fetch_links(url: str) -> list:
    links_found = []
    requests = url_do_request(url)
    soup = BeautifulSoup(requests.text, "html.parser")
    for link in soup.find_all("a"):
        logger.debug(f"link found: {link.get('href')}")
        links_found.append(link.get("href"))
    return links_found


def url_fetch_content(url: str) -> str:
    request = url_do_request(url)
    content = request.content.decode("utf-8")
    return content


def url_get_header(url: str) -> requests.models.Response:
    request = url_do_request(url)
    return request


def url_get_last_modified(url: str) -> str:
    request = url_get_header(url)
    if request is None:
        return None
    last_modified_date = request.headers["Last-Modified"]
    datestring = parsedate_to_datetime(last_modified_date).strftime("%Y-%m-%d")
    return datestring
