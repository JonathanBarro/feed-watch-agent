# feed-watch-agent

A small agent that watches any **RSS or Atom feeds** once a day and **emails you a digest only when something new appears**. No news, no email. It runs for free on **GitHub Actions**, so there is no server to maintain.

Typical uses: tracking security advisories, regulation or tender updates, competitor blogs, product changelogs, job boards with an RSS feed, or any website that publishes a feed.

## How it works

1. **First run:** it remembers everything that already exists and sends nothing, so you are not flooded on day one.
2. **Every run after that:** it downloads the feeds, keeps only the items it has not seen (and that match your keywords, if you set any).
3. **No news:** nothing is sent.
4. **News:** one email with all the new items. The state is saved **only after the email is sent**, so a failed send never loses items.
5. If one feed is down, it logs the error and carries on with the others.

## What can it watch?

**Any website or service that publishes an RSS or Atom feed.** You are not limited to the examples in `config.yaml`; they are just placeholders. Common sources:

| Source | Feed URL pattern |
| --- | --- |
| Most blogs and news sites | `https://<site>/feed/` or `/rss` or `/atom.xml` |
| WordPress sites | `https://<site>/feed/` |
| GitHub releases of any project | `https://github.com/<owner>/<repo>/releases.atom` |
| Reddit community | `https://www.reddit.com/r/<name>/.rss` |
| YouTube channel | `https://www.youtube.com/feeds/videos.xml?channel_id=<id>` |
| Government and regulator portals | Many publish an RSS feed; look for the RSS icon |

Websites that **do not** publish a feed are not supported out of the box, because the agent reads feeds, not web pages. Watching a normal web page (scraping it) is possible as a custom extension.

## Set it up in 5 minutes

1. **Fork or copy this repo** to your own GitHub account.
2. **Choose what to watch** in [`config.yaml`](config.yaml): add your feed URLs and, optionally, keywords.
3. **Add three secrets** in *Settings, Secrets and variables, Actions*:

   | Secret | Value |
   | --- | --- |
   | `SMTP_USER` | The email account that sends the digest (for Gmail, use an [app password](https://support.google.com/accounts/answer/185833)) |
   | `SMTP_PASSWORD` | That account's app password |
   | `RECIPIENTS` | Who receives it, comma-separated: `me@example.com, team@example.com` |

4. **Run it once** from the *Actions* tab (*Feed watch, Run workflow*). After that it runs on its own every weekday. Change the schedule in `.github/workflows/daily.yml`.

Recipients, passwords and addresses never appear in the code or the config file, only in GitHub Secrets.

## Try it locally

```bash
pip install -r requirements.txt
python src/main.py --dry-run     # prints what it would send, saves nothing
python -m unittest discover -s tests
```

To send real emails locally, set `SMTP_USER`, `SMTP_PASSWORD` and `RECIPIENTS` as environment variables first.

## Project structure

```
config.yaml            feeds, keywords, subject title, SMTP host
src/main.py            orchestration: seed, detect news, send, save state
src/feeds.py           download and parse RSS 2.0 / Atom, keyword filter
src/notify.py          build the HTML + plain-text digest, send over SMTP
src/state.py           remembers which items were already reported
tests/                 unit tests (parsing, filtering, seed/new/failed-send flows)
.github/workflows/     daily schedule on GitHub Actions
```

## Need something like this for your own sources?

Feeds with no RSS, sites behind a login, filtering by rules, or alerts on Telegram or Slack instead of email are all straightforward extensions. Get in touch.
