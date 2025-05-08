import logging
import logging.config
import requests
import time
import yaml

from bs4 import BeautifulSoup as bs
from logtail import LogtailHandler
from typing import List, Optional

logger = logging.getLogger("main")


class LogConfig:
    token: Optional[str]
    endpoint: Optional[str]
    level: str

    def __init__(
        self, token: Optional[str], endpoint: Optional[str], level: str = "INFO"
    ):
        if level.upper() in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            self.level = level.upper()
        else:
            self.level = "INFO"

        self.token = token
        self.endpoint = endpoint

        if self.token and self.endpoint:
            handler = LogtailHandler(
                source_token=self.token,
                host=self.endpoint,
            )
        else:
            handler = logging.StreamHandler()

        logger.setLevel(self.level)
        logger.addHandler(handler)


class Eurocore:
    url: str
    user: str
    password: str

    def __init__(self, url: str, user: str, password: str):
        self.url = url
        self.user = user
        self.password = password

        self.url = self.url.strip("/")


class Config:
    user: str
    region: str
    delegate: Optional[str]
    dispatch_id: int
    eurocore: Eurocore
    log: LogConfig

    def __init__(self, path: Optional[str] = None):
        if not path:
            path = "./config.yml"

        with open(path, "r") as in_file:
            data = yaml.safe_load(in_file)

        self.user = data["user"]
        self.region = data["region"]
        self.delegate = data.get("delegate")
        self.dispatch_id = data["dispatch_id"]

        self.eurocore = Eurocore(
            data["eurocore"]["url"],
            data["eurocore"]["user"],
            data["eurocore"]["password"],
        )

        self.log = LogConfig(
            data["log"].get("token"), data["log"].get("endpoint"), data["log"]["level"]
        )


def get_delegate(user: str, region: str) -> str:
    headers = {"User-Agent": user}

    logger.debug("fetching delegate from %s", region)
    delegate = (
        bs(
            requests.get(
                f"https://www.nationstates.net/cgi-bin/api.cgi?region={region}&q=delegate",
                headers=headers,
            ).text,
            "xml",
        )
        .find("DELEGATE")
        .text
    )

    return delegate


def get_nations_not_endorsing(user: str, region: str, delegate: str) -> List[str]:
    headers = {"User-Agent": user}

    logger.debug("retrieving wa nations from %s", region)
    wa_nations = (
        bs(
            requests.get(
                f"https://www.nationstates.net/cgi-bin/api.cgi?region={region}&q=wanations",
                headers=headers,
            ).text,
            "xml",
        )
        .find("UNNATIONS")
        .text.split(",")
    )

    time.sleep(1)

    logger.debug("retrieving delegate endorsements for %s", delegate)
    delegate_endorsements = (
        bs(
            requests.get(
                f"https://www.nationstates.net/cgi-bin/api.cgi?nation={delegate}&q=endorsements",
                headers=headers,
            ).text,
            "xml",
        )
        .find("ENDORSEMENTS")
        .text.split(",")
    )

    return [
        nation
        for nation in wa_nations
        if nation not in delegate_endorsements and nation != delegate
    ]


def login(url: str, user: str, password: str) -> str:
    url = f"{url}/login"

    data = {"username": user, "password": password}

    logger.debug("fetching token from %s", url)
    token = requests.post(url=url, json=data).json()["token"]

    return token


def refresh_nne(url: str, token: str, id: int, nations: List[str]):
    url = f"{url}/dispatches/{id}"

    headers = {"Authorization": f"Bearer {token}"}

    data = {
        "title": "RSC :: Endorse The Delegate",
        "text": None,
        "category": 8,
        "subcategory": 845,
    }

    nations = "".join([f"[nation=noflag]{nation}[/nation]" for nation in nations])

    data["text"] = (
        f"Refreshing, please reload this page in a minute...\n[spoiler]{nations}[/spoiler]"
    )

    resp = requests.put(url, headers=headers, json=data)
    logger.info("dispatch ping status code: %d", resp.status_code)

    with open("dispatch.txt", "r") as in_file:
        data["text"] = in_file.read()

    resp = requests.put(url, headers=headers, json=data)
    logger.info("dispatch reset status code: %d", resp.status_code)


def main():
    config = Config("./config.yml")

    if not config.delegate:
        config.delegate = get_delegate(config.user, config.region)

    nations = get_nations_not_endorsing(
        config.eurocore.user, config.region, config.delegate
    )
    logger.info(
        "number of wa nations in %s not endorsing %s: %d",
        config.region,
        config.delegate,
        len(nations),
    )

    token = login(config.eurocore.url, config.eurocore.user, config.eurocore.password)

    refresh_nne(config.eurocore.url, token, config.dispatch_id, nations)


if __name__ == "__main__":
    main()
