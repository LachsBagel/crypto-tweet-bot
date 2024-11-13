import html
import json
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional, Tuple, Dict, List
import feedparser
import pytz
from anthropic import AsyncAnthropic as Anthropic
from core.config import (
    SUMMARIES_FILE, TWEETS_CONFIG, logger,
    RSS_FEED, TONE_PROMPT, MAIN_AGENT_INSTRUCTIONS,
    MAIN_AGENT_INSTRUCTIONS_PART_TWO, CLAUDE_MODEL, CLAUDE_MAX_TOKENS, ANTHROPIC_API_KEY, TWEETS_ARCHIVE
)
from helpers.content_tracker import ContentTracker
from helpers.file_utils import load_archive, save_archive


def clean_html(raw_html: str) -> str:
    """Cleans HTML tags and formats text"""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    cleantext = html.unescape(cleantext)
    cleantext = ' '.join(cleantext.split())
    return cleantext


def is_within_last_24_hours(published_time: str) -> bool:
    if not published_time:
        return False
    try:
        pub_date = parsedate_to_datetime(published_time)
        now = datetime.now(pytz.UTC)
        return (now - pub_date.replace(tzinfo=pytz.UTC)) <= timedelta(days=1)
    except Exception as e:
        logger.error(f"Error parsing date: {e} for date {published_time}")
        return False


def fetch_crypto_news() -> list:
    """Fetches and parses CoinTelegraph RSS feed"""
    try:
        logger.info("Starting to fetch RSS feed from CoinTelegraph...")
        feed = feedparser.parse(RSS_FEED)

        if not feed.entries:
            logger.error("Feed parsed but no entries found!")
            logger.error(f"Feed status: {feed.status if hasattr(feed, 'status') else 'No status'}")
            return []

        logger.info(f"Successfully fetched feed. Found {len(feed.entries)} total entries")

        news_items = []
        seen_titles = set()

        for i, entry in enumerate(feed.entries, 1):
            logger.info(f"\nProcessing entry {i}/{len(feed.entries)}")

            published_time = entry.get('published') or entry.get('updated')
            logger.info(f"Article timestamp: {published_time}")

            if not published_time:
                logger.warning(f"Entry {i} has no published time, skipping")
                continue

            if not is_within_last_24_hours(published_time):
                logger.info(f"Entry {i} is older than 24 hours, skipping")
                continue

            title = clean_html(entry.title)
            logger.info(f"Processing article: {title}")

            if title in seen_titles:
                logger.info(f"Duplicate title found, skipping: {title}")
                continue

            seen_titles.add(title)

            content = ""
            if hasattr(entry, 'content'):
                content = clean_html(entry.content[0].value)
            elif hasattr(entry, 'summary'):
                content = clean_html(entry.summary)
            else:
                logger.warning(f"No content found for article: {title}")

            article = {
                'title': title,
                'link': entry.link,
                'published': published_time,
                'content': content
            }

            news_items.append(article)
            logger.info(f"Added article to news_items. Current count: {len(news_items)}")

        logger.info(f"\nFinal processing results:")
        logger.info(f"Total entries in feed: {len(feed.entries)}")
        logger.info(f"Articles within last 24h: {len(news_items)}")
        logger.info(f"Unique titles processed: {len(seen_titles)}")

        return news_items

    except Exception as e:
        logger.error(f"Error fetching news: {str(e)}")
        logger.exception("Full traceback:")
        return []


async def generate_summary(article: dict, api_key: str) -> Optional[str]:
    """Generate summary using Claude"""
    client = Anthropic(api_key=api_key)

    prompt = f"""Summarize this crypto news article in a clear, informative way that captures key points and market 
    implications. Focus on facts, developments, and potential impact on the crypto ecosystem. Keep the summary 
    detailed but concise.

    Title: {article['title']}
    Content: {article['content']}

    Provide the summary in a single paragraph without any prefixes or labels."""

    try:
        message = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        return message.content[0].text.strip()

    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        logger.exception("Full traceback:")
        return None


def read_example_tweets() -> str:
    """Read example tweets from config"""
    try:
        with open(TWEETS_CONFIG, 'r') as f:
            config = json.load(f)
            examples = config['pro_crypto']  # Directly access pro_crypto since we only use this now
            return "\n".join(f"Example {i + 1}: {tweet}" for i, tweet in enumerate(examples))
    except Exception as e:
        logger.error(f"Error reading example tweets: {e}")
        return ""


def format_market_context(trending_pools: list) -> str:
    """Format market data into readable context"""
    context = "Current Market Activity:\n\n"
    for pool in trending_pools[:5]:
        volume_24h = float(pool['volumes']['h24'] or 0)
        buys_24h = pool['transactions']['h24']['buys']
        sells_24h = pool['transactions']['h24']['sells']
        price_change = float(pool['price_changes']['h24'] or 0)

        context += (
            f"Pool: {pool['name']}\n"
            f"24h Change: {price_change:+.2f}%\n"
            f"24h Volume: ${volume_24h:,.2f}\n"
            f"Buy/Sell Ratio: {pool['buy_sell_ratio']:.2f} ({buys_24h} buys / {sells_24h} sells)\n"
            f"Market Cap: ${float(pool['market_cap'] or 0):,.2f}\n\n"
        )
    return context


async def generate_tweet(articles: list, tweets: list, trending_pools: list, api_key: str) -> Optional[Tuple[str, str]]:
    """Generate a pro-crypto tweet using comprehensive market context with retry logic"""
    client = Anthropic(api_key=api_key)
    content_tracker = ContentTracker()

    # Load tweet history
    tweets_archive = load_archive(TWEETS_ARCHIVE)
    previous_tweets = tweets_archive.get('tweets', [])

    # Analyze crypto Twitter discussion themes
    social_themes = {}
    high_engagement_tweets = []

    if tweets:  # If we have tweets from target users
        # Sort by engagement
        engaged_tweets = sorted(tweets, key=lambda x: x['likes'] + x['retweets'], reverse=True)

        # Analyze themes from top engaged tweets
        for tweet in engaged_tweets[:5]:
            high_engagement_tweets.append(tweet)

            # Extract topics/themes
            text = tweet['text'].lower()
            for category, keywords in ContentTracker.CATEGORIES.items():
                if any(keyword in text for keyword in keywords):
                    social_themes[category] = social_themes.get(category, 0) + 1

        logger.info(f"Popular themes on crypto Twitter: {social_themes}")

    # Get fresh categories and analyze patterns
    # Get fresh categories and prioritize based on social trends
    fresh_categories = list(content_tracker.get_fresh_categories())
    if social_themes:
        # Prioritize categories that are trending on Twitter but not overused in our tweets
        fresh_categories.sort(key=lambda x: social_themes.get(x, 0), reverse=True)

    logger.info(f"Fresh categories (prioritized): {fresh_categories}")

    # Track categories we've tried
    tried_categories = set()
    max_retries = 3

    for attempt in range(max_retries):
        logger.info(f"\nAttempt {attempt + 1}/{max_retries}")

        # Analyze recent patterns to avoid
        recent_patterns = {
            'tokens': set(),
            'phrases': set(),
            'themes': set()
        }

        if previous_tweets:
            last_5_tweets = previous_tweets[-5:]
            for tweet in last_5_tweets:
                # Track tokens
                for token in ['Bitcoin', 'BTC', 'ETH', 'Ethereum', 'SOL', 'Solana']:
                    if token.lower() in tweet['tweet'].lower():
                        recent_patterns['tokens'].add(token)

                # Track starting phrases
                tweet_start = tweet['tweet'].split()[0].lower()
                recent_patterns['phrases'].add(tweet_start)

                # Track themes
                if any(price_word in tweet['tweet'].lower() for price_word in ['price', '$', 'ath', 'high', 'low']):
                    recent_patterns['themes'].add('price')

        # Select a fresh category we haven't tried yet
        available_categories = [cat for cat in fresh_categories if cat not in tried_categories]
        if not available_categories:
            logger.info("No more fresh categories to try")
            return None

        focus_category = available_categories[0]
        tried_categories.add(focus_category)
        logger.info(f"Trying category: {focus_category}")

        # Filter articles based on current category
        filtered_articles = []
        for article in articles:
            categories = content_tracker._categorize_content(article['title'] + ' ' + article.get('summary', ''))

            if focus_category in categories:
                # Skip if article mainly discusses recently mentioned tokens
                if not any(token.lower() in article['title'].lower() for token in recent_patterns['tokens']):
                    filtered_articles.append(article)

        if not filtered_articles:
            logger.info(f"No articles available for category {focus_category}, trying next category")
            continue

        # Prepare context sections
        context_sections = []

        # Previous tweets context
        if previous_tweets:
            context_sections.append(f"""
                    Recent tweets to avoid repeating:
                    {format_previous_tweets(previous_tweets[-3:])}

                    DO NOT:
                    - Use similar opening phrases: {', '.join(recent_patterns['phrases'])}
                    - Focus on recently mentioned tokens: {', '.join(recent_patterns['tokens'])}
                    - Repeat recent themes: {', '.join(recent_patterns['themes'])}
                    """)

        # Social context section
        if high_engagement_tweets:
            context_sections.append("""
                    Current Crypto Twitter Discussion:
                    These tweets are getting high engagement - consider their themes but create unique perspective:
                    """)
            for tweet in high_engagement_tweets:
                context_sections.append(f"""
                        @{tweet['username']} ({tweet['likes']} likes, {tweet['retweets']} RTs):
                        {tweet['text']}
                        """)

        # Category focus with strong guidance
        context_sections.append(f"""
                FOCUS CATEGORY: {focus_category.upper()}
                This theme {f"is trending on Crypto Twitter with {social_themes.get(focus_category, 0)} high-engagement tweets" if social_themes.get(focus_category) else "needs more attention on Crypto Twitter"}

        Guidelines for this category:
        - Highlight specific developments and milestones
        - Focus on user impact and real-world applications
        - Use concrete details and numbers
        - Tell a story rather than make general observations
        - Create engagement through insight, not price speculation
        - Consider but don't copy the trending perspectives on Twitter
        
        IMPORTANT: Avoid these opening words/phrases:
        {', '.join(recent_patterns['phrases'])}
        """)

        # Articles context
        articles_context = "Relevant Articles:\n\n"
        for idx, article in enumerate(filtered_articles[:3], 1):
            articles_context += f"""Article {idx}:
            Title: {article['title']}
            Summary: {article['summary']}\n\n"""
        context_sections.append(articles_context)

        # Market context (only if relevant to chosen category)
        if focus_category in ['adoption', 'defi', 'infrastructure']:
            context_sections.append(
                f"Market Activity (use only if relevant to {focus_category}):\n{format_market_context(trending_pools)}")

        # Construct the prompt
        prompt = f"""{TONE_PROMPT}

        {MAIN_AGENT_INSTRUCTIONS}

        {' '.join(context_sections)}

        IMPORTANT REQUIREMENTS:
        1. Focus exclusively on {focus_category} category
        2. Do not mention price unless absolutely necessary for context
        3. Pick ONE specific development or story to highlight
        4. Use concrete details from the provided articles
        5. Create engagement through insight and analysis
        6. Keep the tone optimistic but grounded in facts
        7. Avoid generic market commentary
        8. Use fresh metaphors and expressions
        9. DO NOT start tweet with any of these words: {', '.join(recent_patterns['phrases'])}
        10. Consider but don't duplicate trending Twitter discussions
        11. Add unique perspective to ongoing conversations

        {MAIN_AGENT_INSTRUCTIONS_PART_TWO}"""

        try:
            logger.info("Generating tweet with Claude...")
            message = await client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response = message.content[0].text

            reasoning = ""
            tweet_text = ""

            for line in response.split('\n'):
                if line.startswith('REASONING: '):
                    reasoning = line.replace('REASONING: ', '')
                elif line.startswith('TWEET: '):
                    tweet_text = line.replace('TWEET: ', '')

            if tweet_text:
                # Verify the generated tweet doesn't repeat patterns
                if any(phrase in tweet_text.lower().split()[0] for phrase in recent_patterns['phrases']):
                    logger.warning(f"Generated tweet uses recent phrases, trying different category")
                    continue

                if any(token.lower() in tweet_text.lower() for token in recent_patterns['tokens']):
                    logger.warning(f"Generated tweet mentions recent tokens, trying different category")
                    continue

                return tweet_text.strip(), reasoning.strip()

        except Exception as e:
            logger.error(f"Error generating tweet: {e}")
            logger.exception("Full traceback:")
            continue

    logger.error("Failed to generate unique tweet after all retries")
    return None


def format_previous_tweets(tweets: List[Dict]) -> str:
    """Format previous tweets for context"""
    result = ""
    for i, tweet in enumerate(tweets, 1):
        result += f"{i}. {tweet['tweet']}\n"
        if tweet.get('reasoning'):
            result += f"   Context: {tweet['reasoning']}\n\n"
    return result


async def fetch_and_generate_summaries() -> bool:
    """Fetch new articles and generate summaries"""
    logger.info("\n=== Starting Article Fetch and Summary Generation ===")

    # Load existing summaries
    summaries_archive = load_archive(SUMMARIES_FILE)
    logger.info(f"Loaded existing summaries archive. Current items: {len(summaries_archive['items'])}")
    logger.info(f"Current processed URLs: {len(summaries_archive['processed_urls'])}")

    # Fetch new articles
    logger.info("\n=== Fetching New Articles ===")
    all_news = fetch_crypto_news()
    logger.info(f"Fetched {len(all_news)} articles from feed")

    if not all_news:
        logger.error("No articles returned from fetch_crypto_news!")
        return False

    # Filter unprocessed articles
    unprocessed_news = [
        article for article in all_news
        if article['link'] not in summaries_archive['processed_urls']
    ]

    logger.info(f"\nFiltering results:")
    logger.info(f"Total articles fetched: {len(all_news)}")
    logger.info(f"Unprocessed articles: {len(unprocessed_news)}")

    successful_summaries = 0
    if unprocessed_news:
        logger.info(f"\nStarting summary generation for {len(unprocessed_news)} articles")

        for i, article in enumerate(unprocessed_news, 1):
            logger.info(f"\nProcessing article {i}/{len(unprocessed_news)}")
            logger.info(f"Title: {article['title']}")
            logger.info(f"URL: {article['link']}")

            # Await the summary generation
            summary = await generate_summary(article, ANTHROPIC_API_KEY)

            if summary:
                logger.info("Summary generated successfully")
                article_data = {
                    'title': article['title'],
                    'link': article['link'],
                    'published': article['published'],
                    'summary': summary
                }
                summaries_archive['items'].append(article_data)
                summaries_archive['processed_urls'].append(article['link'])
                successful_summaries += 1
            else:
                logger.error(f"Failed to generate summary for article: {article['title']}")

        logger.info(f"\nSaving updated archive:")
        logger.info(f"New successful summaries: {successful_summaries}")
        logger.info(f"Total items in archive: {len(summaries_archive['items'])}")

        save_archive(summaries_archive, SUMMARIES_FILE)
        return True
    else:
        logger.info("No new articles to process")
        return False
