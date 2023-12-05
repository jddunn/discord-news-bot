import os, sys
import requests
import lxml
import time

from datetime import datetime
from dateutil.parser import parse

from bs4 import BeautifulSoup

import json

from urllib.parse import urlparse

from operator import itemgetter

# from tabulate import tabulate
import pickle
import json

# Selenium
from selenium import webdriver

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from selenium.webdriver.chrome.service import Service as ChromeService

from fake_useragent import UserAgent

# Discord imports
import discord
from discord.ext import commands, tasks
from discord.ext import commands

# HTML to text
import goose3 as goose

# NLP / Summarizer
from _summarizer import summarizer

ua = UserAgent()
g = goose.Goose()

# Download appropriate version of Chromedriver from here:
# https://chromedriver.chromium.org/downloads
# and place in same directory as this script
CHROME_PATH = r"./chromedriver.exe"
service = Service(executable_path=CHROME_PATH)

from webdriver_manager.chrome import ChromeDriverManager

chrome_options = Options()
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--ignore-certificate-errors")
chrome_options.add_argument("--allow-running-insecure-content")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--proxy-bypass-list=*")

# read config
with open("config.json", "r") as jsonfile:
    config = json.load(jsonfile)

# print(config)

TOKEN = config["token"]
US_NEWS_CHANNEL = int(config["us_news_channel_id"])
WORLD_NEWS_CHANNEL = int(config["world_news_channel_id"])
US_NEWS_LIMIT = config["us_news_limit"]
WORLD_NEWS_LIMIT = config["world_news_limit"]
US_NEWS_POST_TIMER = config["us_news_post_timer"]
WORLD_NEWS_POST_TIMER = config["world_news_post_timer"]

US_NEWS_LINK = "https://news.google.com/topstories?hl=en-US&gl=US&ceid=US:en"
WORLD_NEWS_LINK = "https://news.google.com/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US%3Aen"

intents = discord.Intents.default()
client = discord.Client(intents=intents)
# client = commands.Bot(command_prefix = '!!')


def driver_interceptor(request: dict) -> None:
    """
    Intercepts a request and modifies the headers
    to use a randomized fake user agent.

    Args:
        request (dict): Request object from Selenium driver
    """
    request.headers["User-Agent"] = ua.random


class NewsBot:
    """
    Discord bot that scrapes Google News and posts
    summaries to Discord channels defined in config.json.

    Results are cached in pickle files locally to avoid
    redundant posts (though some headlines can be repeated
    still).
    """

    def __init__(self) -> None:
        self._first_time_running_us_news = True
        self._first_time_running_world_news = True

        # WebdriverManager library automates the process of getting Chromedriver, but it'll
        # be faster initialization if you do download it manually and place it in the dir
        # Wasn't able to get the webdriver-manager library working properly with the Discord
        # task looping, so we'll manually download the driver and place it in the dir

        # self.driver = webdriver.Chrome(
        #     service=ChromeService(ChromeDriverManager().install()),
        #     options=chrome_options,
        # )

        # Create cache / data directory if it does not exist
        if not os.path.exists("./data"):
            os.makedirs("./data")

        if CHROME_PATH:
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            # If we didn't provide a chrome path it will look for chromedriver in PATH
            self.driver = webdriver.Chrome(options=chrome_options)
        # print(self.driver)
        # Make Selenium wait 3 seconds before extracting contents
        self.driver.implicitly_wait(3)
        # Intercept requests and modify headers
        self.driver.request_interceptor = driver_interceptor
        return

    async def scan_us_news(self, url: str = US_NEWS_LINK) -> list:
        """
        Scrape Google News for US news headlines, then searches the headline
        in Google to get the article page and scrape that content. The content
        of the article is then summarized and collected in a list of results,
        which is posted to Discord.

        Args:
            url (str, optional): URL to scrape for news; defaults to US_NEWS_LINK.

        Returns:
            list: List of US news results with date, title, and article summary.
        """
        r = requests.get(url, headers={"User-Agent": ua.random})
        soup = BeautifulSoup(r.text, "lxml", from_encoding="utf-8")
        # newscards = soup.find_all("div", {"class": "KDoq1"})
        headlines = soup.find_all("h4", {"class": "iTin5e"})
        dates = soup.find_all("time", {"class": "hvbAAd"})
        # print(len(headlines), 'headlines', len(dates), 'dates found.')
        # newscards = newscards[: US_NEWS_LIMIT]
        headlines = headlines[:US_NEWS_LIMIT]
        dates = dates[:US_NEWS_LIMIT]

        results = []
        pickle_cache = []
        # Gather results and check cache
        for i, (date, title) in enumerate(zip(dates, headlines)):
            results.append([date.text, title.text])
        results = [list(x) for x in set(tuple(x) for x in results)]
        if os.path.isfile("./data/cache_us_news.pkl"):
            same = True
            with open("./data/cache_us_news.pkl", "rb") as file:
                pickle_cache = pickle.load(open("./data/cache_us_news.pkl", "rb"))
                same = self._check_pickle_cache_with_results(pickle_cache, results)
            if same:
                print("No new US news to update.")
                return
            else:
                with open("./data/cache_us_news.pkl", "wb") as file:
                    pickle.dump(results, file)
                results = await self.scrape_news_links(results)
                results = await self.summarize_news(results)
                await self.post_us_news(results)
                return
        else:
            # print("Caching new results to pickle file.")
            with open("./data/cache_us_news.pkl", "wb") as file:
                pickle.dump(results, file)
            results = await self.scrape_news_links(results)
            results = await self.summarize_news(results)
            await self.post_us_news(results)
        print(results)
        return results

    async def scan_world_news(self, url: str = WORLD_NEWS_LINK) -> list:
        """
        Scrape Google News for world news headlines, then searches the headline
        in Google to get the article page and scrape that content. The content
        of the article is then summarized and collected in a list of results,
        which is posted to Discord.

        Args:
            url (str, optional): URL to scrape for news; defaults to WORLD_NEWS_LINK.

        Returns:
            list: List of US news results with date, title, and article summary.
        """
        r = requests.get(url)
        soup = BeautifulSoup(r.text, "lxml")

        # newscards = soup.find_all("div", {"class": "NWHX8c"})
        headlines = soup.find_all("h4", {"class": "gPFEn"})
        dates = soup.find_all("time", {"class": "hvbAAd"})
        print(len(headlines), "headlines", len(dates), "dates found for world news.")
        # newscards = newscards[: WORLD_NEWS_LIMIT]
        headlines = headlines[:WORLD_NEWS_LIMIT]
        dates = dates[:WORLD_NEWS_LIMIT]

        pickle_cache = []
        results = []

        # Gather results and check cache
        for i, (date, title) in enumerate(zip(dates, headlines)):
            results.append([date.text, title.text])
        # Filter results for unique values by title and date
        results = [list(x) for x in set(tuple(x) for x in results)]
        if os.path.isfile("./data/cache_world_news.pkl"):
            same = True
            with open("./data/cache_world_news.pkl", "rb") as file:
                pickle_cache = pickle.load(open("./data/cache_world_news.pkl", "rb"))
                same = self._check_pickle_cache_with_results(pickle_cache, results)
            if same:
                print("No new world news to update.")
                return
            else:
                with open("./data/cache_world_news.pkl", "wb") as file:
                    pickle.dump(results, file)
                results = await self.scrape_news_links(results)
                results = await self.summarize_news(results)
                await self.post_world_news(results)
        else:
            print("Caching new results to pickle file.")
            with open("./data/cache_world_news.pkl", "wb") as file:
                pickle.dump(results, file)
                results = await self.scrape_news_links(results)
                results = await self.summarize_news(results)
                await self.post_world_news(results)
        print(results)
        return results

    async def scrape_news_links(self, news_list: list) -> list:
        """
        Scrape the links of the results from Google News
        with Selenium, and makes summaries of the news contents.

        Args:
            news_list (list): List of results from Google News scrape

        Returns:
            list: List of same results with scraped contents appended
        """
        results = []

        for i, each in enumerate(news_list):
            date = each[0]
            title = each[1]
            try:
                # Google the title of the news article to get the link and scrape that
                link = self.google(title + " news")
                print("Scrape: ", i, date, title, link)
                self.driver.implicitly_wait(3)
                # # Intercept requests and modify headers
                self.driver.request_interceptor = driver_interceptor
                # wait = WebDriverWait(self.driver, 3)
                self.driver.get(link)
                body = self.driver.find_element(By.TAG_NAME, "body")
                body = body.get_attribute("innerHTML")
                body = g.extract(raw_html=body)
                body = body.cleaned_text
                print("Cleaned text extracting from goose: ", body)
                # self.driver.close()
                results.append([date, title, link, body])
            except Exception as e:
                # self.driver.close()
                print("Err getting scrape for " + title + ": ", e)
                pass
        print("Finished scrape: ", len(results))
        return results

    async def summarize_news(self, news_list: list) -> list:
        """
        Summarizes the news contents of a list of results.

        Args:
            news_list (list): List of results from Google News scrape

        Returns:
            list: List of same results with summaries appended
        """
        results = []
        print("Summarizing: ", len(news_list), "articles.")
        for i, each in enumerate(news_list):
            print("Summarize: ", i, each)
            date = each[0]
            title = each[1]
            link = each[2]
            body = each[3]
            article_summary = ""
            # print("Summarizing: ", i, date, title, link)
            article_summary = summarizer.summarize(body)
            print("Finished summary: ", article_summary)
            results.append([date, title, link, article_summary])
        return results

    async def post_us_news(self, data: list, channel_id: int = US_NEWS_CHANNEL) -> None:
        """
        Formats and posts a list of US news results to
        Discord channel defined in config.json.

        Args:
            data (list): List of US news results
        """
        title = ""
        descr = ""
        # descr += "------------------------------------------------------"
        for i, each in enumerate(data):
            descr += "--------------------------------------------------------\n"
            descr += "**" + data[i][1] + "**" + "\n" + "*" + data[i][0] + "*" + "\n"
            # descr += "\n------------------------------\n"
            descr += data[i][2].replace("www.", "") + "\n\n"
            # descr += "\n------------------------------\n"
            # descr += pickle_data[i][3]
            # descr += "\n\t-\t\n"
            descr += data[i][3] + "\n"
        # Ensure descr is under 4096 chars for Discord form submission
        descr = descr[:4096]
        now = time.time()
        ts = datetime.fromtimestamp(now).strftime("%m/%d/%Y, %H:%M:%S")
        message = "**🇺🇸 📰  LATEST US NEWS STORIES  📰 🇺🇸**\t*(" + str(ts) + ")*"

        news_embed = discord.Embed(title=title, description=descr)

        print("Posting: ", message)

        # await client.wait_until_ready()

        channel = client.get_channel(channel_id)

        await channel.send(message, embed=news_embed)
        print("Posted update to US news.")
        return

    async def post_world_news(
        self, data: list, channel_id: int = WORLD_NEWS_CHANNEL
    ) -> None:
        """
        Formats and posts a list of world news results to
        Discord channel defined in config.json.

        Args:
            data (list): _description_
        """
        title = ""
        descr = ""
        # descr += "------------------------------------------------------"

        for i, each in enumerate(data):
            descr += "--------------------------------------------------------\n"
            descr += "**" + data[i][1] + "**" + "\n" + "*" + data[i][0] + "*" + "\n"
            # descr += "\n------------------------------\n"
            descr += data[i][2].replace("www.", "") + "\n\n"
            # descr += "\n------------------------------\n"
            # descr += pickle_data[i][3]
            # descr += "\n\t-\t\n"
            descr += data[i][3] + "\n"
        # Ensure descr is under 4096 chars for Discord form submission
        descr = descr[:4096]
        now = time.time()
        ts = datetime.fromtimestamp(now).strftime("%m/%d/%Y, %H:%M:%S")
        message = "**🌎 📰  LATEST WORLD NEWS STORIES  📰 🌎**\t*(" + str(ts) + ")*"

        news_embed = discord.Embed(title=title, description=descr)

        print("Posting: ", message)
        # await client.wait_until_ready()

        channel = client.get_channel(channel_id)

        await channel.send(message, embed=news_embed)
        print("Posted update to world news.")
        return

    def _check_pickle_cache_with_results(
        self, pickle_cache: list, results: list
    ) -> bool:
        """
        Check if the pickle data is the same as the results.

        It checks for all items, and if it detects any difference
        at all, it returns False.

        Args:
            pickle_data (list): List of results read from pickle file
            results (list): List of results from Google News scrape

        Returns:
            bool: True if same, False if different
        """
        same = True
        for x, y in zip(pickle_cache, results):
            if x is y:
                pass
            elif type(x == list) and (type(y) == list):
                # We only need to check for one item,
                # being the title, since the date / time
                # will probably be different on each scrape
                # print(x, y, len(x), len(y))
                for i in range(1, 2):
                    if x[i] == y[i]:
                        pass
                    else:
                        same = False
            else:
                same = False
        return same

    def google(self, query: str) -> str:
        """
        Google search for a query string and return the
        first result link. We will use this to get the
        news article from a headline as the query.

        Args:
            query (str): Query string

        Returns:
            str: First result link
        """
        # Wait 3 seconds before we make a Google request
        # to avoid getting blocked
        # print("Googling link: ", q)
        time.sleep(3)
        headers = {
            "User-Agent": ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        query = "+".join(query.split())
        url = "https://www.google.com/search?q=" + query
        # print(query)
        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")
        links = soup.find_all("div", "yuRUbf")
        link = ""  # Result to return
        for l in links:
            _link = l.find("a", href=True)
            link = _link["href"]
            # if link has youtube in it, skip it
            if "youtube" in link:
                continue
            else:
                break
        print("Link found from Google for query: ", query, link)
        return link

    @tasks.loop(seconds=US_NEWS_POST_TIMER)
    async def scan_us_news_loop(self):
        """
        Scan Google News for US news, and summarize and
        post to Discord.
        """
        if self._first_time_running_us_news:
            print("Initializing US news summarization loop.")
            self._first_time_running_us_news = False
            # Add any logic you want on first initialization of loop
            await self.scan_us_news()
            return
        else:
            print("Scanning US news.")
            await self.scan_us_news()
            return

    @tasks.loop(seconds=WORLD_NEWS_POST_TIMER)
    async def scan_world_news_loop(self) -> None:
        """
        Scan Google News for world news, and summarize and
        post to Discord.
        """
        if self._first_time_running_world_news:
            print("Initializing world news summarization loop.")
            self._first_time_running_world_news = False
            # Add any logic you want on first initialization of loop
            await self.scan_world_news()
            return
        else:
            print("Scanning world news.")
            await self.scan_world_news()
            return


# @client.event
# async def on_disconnect():
#     print("Shutting down!")
#     bot.driver.quit()
#     await client.close()


# @scan_us_news.before_loop
# @scan_world_news.before_loop
async def before() -> None:
    """
    Logic for before Discord bot is initialized.
    """
    await client.wait_until_ready()
    print(
        datetime.now().strftime("%Y-%m-%d %I:%M:%S:%f %p")
        + " Time has finished waiting"
    )


@client.event
async def on_ready() -> None:
    """
    Logic once Discord bot is initialized.
    """
    await client.change_presence(
        status=discord.Status.online, activity=discord.Game("news scanner.")
    )
    print(
        datetime.now().strftime("%Y-%m-%d %I:%M:%S:%f %p")
        + " \nDiscord News Bot is ONLINE, listening for actions and scanning..\n"
    )
    # client.start(bot.scan_us_news_loop())
    # client.start(bot.scan_world_news_loop())
    client.loop.create_task(bot.scan_us_news_loop())
    client.loop.create_task(bot.scan_world_news_loop())


"""
Initialize bot.
"""
if __name__ == "__main__":
    bot = NewsBot()
    client.run(TOKEN)
