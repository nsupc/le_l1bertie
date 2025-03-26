import argparse
import logging
import logging.config
import requests
import time

from bs4 import BeautifulSoup as bs
from typing import List, Literal


class Cli:
    region: str
    delegate: str
    eurocore_url: str
    eurocore_user: str
    eurocore_password: str
    dispatch_id: int
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]


def parse_args() -> Cli:
    parser = argparse.ArgumentParser(
        description="le l1bertie: a eurocore helper script to refresh an nne dispatch"
    )

    parser.add_argument(
        "-r",
        "--region",
        type=str,
        required=True,
        help="region to check for nations not endorsing [delegate]",
    )

    parser.add_argument(
        "-d",
        "--delegate",
        type=str,
        required=True,
        help="desired delegate/target nation",
    )

    parser.add_argument(
        "-e",
        "--eurocore-url",
        type=str,
        required=True,
        help="base url of eurocore instance",
    )

    parser.add_argument(
        "-u", "--eurocore-user", type=str, required=True, help="eurocore username"
    )

    parser.add_argument(
        "-p",
        "--eurocore-password",
        type=str,
        required=True,
        help="eurocore user password",
    )

    parser.add_argument(
        "-i",
        "--dispatch-id",
        type=int,
        required=True,
        help="NS dispatch ID for NNE to refresh",
    )

    parser.add_argument(
        "-l",
        "--log-level",
        type=str,
        required=False,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
    )

    cli = parser.parse_args(namespace=Cli)

    cli.region = cli.region.strip().lower().replace(" ", "_")
    cli.delegate = cli.delegate.strip().lower().replace(" ", "_")
    cli.eurocore_url = cli.eurocore_url.strip("/")

    return cli


def get_nations_not_endorsing(user: str, region: str, delegate: str) -> List[str]:
    headers = {"User-Agent": user}

    logging.debug("retrieving wa nations from %s", region)
    wa_nations = (
        bs(
            requests.get(
                "https://www.nationstates.net/cgi-bin/api.cgi?region=europeia&q=wanations",
                headers=headers,
            ).text,
            "xml",
        )
        .find("UNNATIONS")
        .text.split(",")
    )

    time.sleep(1)

    logging.debug("retrieving delegate endorsements for %s", delegate)
    delegate_endorsements = (
        bs(
            requests.get(
                "https://www.nationstates.net/cgi-bin/api.cgi?nation=upc&q=endorsements",
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

    logging.debug("fetching token from %s", url)
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
    logging.info("dispatch ping status code: %d", resp.status_code)

    with open("dispatch.txt", "r") as in_file:
        data["text"] = in_file.read()

    resp = requests.put(url, headers=headers, json=data)
    logging.info("dispatch reset status code: %d", resp.status_code)


def main():
    cli = parse_args()
    logging.config.fileConfig("logging.conf")
    logging.getLogger().setLevel(cli.log_level)

    nations = get_nations_not_endorsing(cli.eurocore_user, cli.region, cli.delegate)
    logging.info(
        "number of wa nations in %s not endorsing %s: %d",
        cli.region,
        cli.delegate,
        len(nations),
    )

    token = login(cli.eurocore_url, cli.eurocore_user, cli.eurocore_password)

    refresh_nne(cli.eurocore_url, token, cli.dispatch_id, nations)


if __name__ == "__main__":
    main()
