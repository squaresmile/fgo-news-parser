import urllib.parse
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import httpx
import orjson
from bs4 import BeautifulSoup


class Region(str, Enum):
    NA = "NA"
    JP = "JP"


@dataclass
class ParsedNews:
    title: str
    date: str
    relative_url: str
    full_url: str


@dataclass
class DiscordWebhook:
    webhook_urls: list[str]


WEBVIEW_URLS = {
    Region.JP: "https://webview.fate-go.jp/",
    Region.NA: "https://webview.fate-go.us/",
}


def parse_news_text(page_url: str, html_string: str) -> list[ParsedNews]:
    soup = BeautifulSoup(html_string, "html.parser")
    news_list = soup.find("ul", class_="list").find_all("li")

    parsed_news: list[ParsedNews] = []
    for news in news_list:
        relative_url = news.find("a")["href"]
        if "info/tips" not in relative_url:
            parsed_news.append(
                ParsedNews(
                    title=news.find(class_="title").text,
                    date=news.find(class_="date").text,
                    relative_url=relative_url,
                    full_url=urllib.parse.urljoin(page_url, relative_url),
                )
            )

    return parsed_news


def main(region: Region) -> None:
    webview_url = WEBVIEW_URLS[region]
    saved_file = Path(f"parsed_news_{region}.json").resolve()

    r = httpx.get(webview_url)
    parsed_news = parse_news_text(webview_url, r.content.decode("utf-8"))

    if saved_file.exists():
        old_parsed_news = [
            ParsedNews(**new) for new in orjson.loads(saved_file.read_bytes())
        ]
        old_relative_urls = {new.relative_url for new in old_parsed_news}
    else:
        old_relative_urls = set()

    with open("discord_webhook.json", "rb") as fp:
        discord_webhook = DiscordWebhook(**orjson.loads(fp.read()))

    for news in parsed_news:
        if news.relative_url not in old_relative_urls:
            message = f"{news.date} {news.title}\n{news.full_url}"
            webhook_content = {
                "content": message,
                "username": f"FGO {region} news",
                "avatar_url": "https://i.imgur.com/hiTlEqA.png",
            }

            for webhook_url in discord_webhook.webhook_urls:
                httpx.post(webhook_url, data=webhook_content)

    saved_file.write_bytes(orjson.dumps(parsed_news, option=orjson.OPT_INDENT_2))


if __name__ == "__main__":
    main(Region.NA)
    main(Region.JP)
