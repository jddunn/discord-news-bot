# Discord News Bot

## Intro

A bot for Discord that scrapes Google News for US and world news for headlines. The headlines are then searched for in Google, and the article texts are scraped with Selenium (with ChromeDriver using Chrome), then summarized (extractive summarization) with [BERT](https://huggingface.co/docs/transformers/model_doc/bert) using Hugging Face's transformer pipeline. Article contents are extracted from HTML using [Goose](https://github.com/grangier/python-goose).

The headlines, dates, and article summaries are posted to the Discord channel(s) specified in the config file as nicely formatted embeds.

<img src="https://i.imgur.com/rVxCIYn.png" width="350">

<img src="https://i.imgur.com/sOYfhb4.png" width="350">

## Technical notes

Headlines and dates of articles are saved in a local cache via pickle data (in two separate files for US and world news). The bot checks Google News on a looped timer, and if a headline or date is new (different than what's stored in the pickled cache), then it'll make new summaries and post to Discord. It's limited in that *any* difference in a single date or headline will result in the bot posting all the found headlines, so it's still possible to have repeated ones. 

You can use `bert-extractive-summarizer` (by calling `summarize_optimal` method in `_summarizer.py`), which optimally summarizes by clustering sentence embeddings (see paper: [https://arxiv.org/abs/1906.04165](https://arxiv.org/abs/1906.04165)). With this method you do not need to give a minimum / maximum length to BERT's model, as it calculates the optimal number of sentences in the summary. However, I was unable to get this library working asynchronously in the Discord task loop consistently, so this method is not used. In the future it'll probably be better to implement the paper's architecture in our own code instead of trying to use this library.

BERT summarization has limitations; the input length is limited to 512 tokens in the model. For longer articles, we should dynamically switch summarization implementations, because it'll be more accurate for large contexts. [LexRank](https://github.com/crabcamp/lexrank) is a good choice.

## Config / set-up

Create a virtual env or install the requirements directly:
`pip install -r requirements.txt`

Modify these values in `config.json`:

- `token`: Your Discord bot token (from [https://discord.com/developers/applications/](https://discord.com/developers/applications/))

- `us_news_channel_id`: The channel ID to post US news to

- `world_news_channel_id`: The channel ID to post world news to

Create and invite the bot to your Discord server with an invite link like the one below (modify CLIENT_ID with your application / bot from the link above):
`https://discord.com/oauth2/authorize?client_id=CLIENT_ID&scope=bot&permissions=1099511627775`

This invite link has permissions scope for **everything** that a bot can do. You probably will want to modify the permissions scope to only be able to view and post in channels (all that is necessary for this bot) for security.

Download the appropriate version of chromedriver for your machine setup from here: [https://chromedriver.chromium.org/downloads](https://chromedriver.chromium.org/downloads).

Note: Logic for using [webdriver-manager library](https://pypi.org/project/webdriver-manager/) is commented out in the code. That library's Selenium instance wasn't able to work with the Discord bot, so we'll have to manually get Chromedriver.

## Running the bot

`python discord-news-bot.py`

## Development

### NLP / Summarization

If you want to use another custom model for summarization, you can modify which model and tokenizer to use at the top of the code in `_summarizer.py`.

The Summarizer.summarize_optimal() method accepts two arguments, a string of text, and an optional int for max number of sentences to generate in the summary. The max sentence number is defaulted to `K_MAX` defined in `_summarizer.py`, which is currently set to 4. You can modify the summarizer to use this method in `discord_news.py` if you prefer.

### Linting

```
pip install black
black .
```