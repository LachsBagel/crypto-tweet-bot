from typing import List, Dict
import time
import tweepy
from requests.exceptions import ConnectionError, Timeout
from urllib3.exceptions import ProtocolError
from core.config import (logger, TARGET_USERNAMES, BEARER_TOKEN, API_KEY,
                         API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

from helpers.tweets_cache import TweetCache


class TwitterAPI:
    def __init__(self):
        self.client = None
        self.is_configured = False
        self.tweet_cache = TweetCache()
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        self.setup_api()

    def _make_twitter_request(self, request_func):
        """Helper method to make Twitter API requests with retry logic"""
        for attempt in range(self.max_retries):
            try:
                return request_func()
            except (ConnectionError, ProtocolError, Timeout) as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed after {self.max_retries} attempts: {str(e)}")
                    raise
                logger.warning(f"Connection error (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                time.sleep(self.retry_delay * (attempt + 1))
            except tweepy.errors.TooManyRequests:
                logger.warning("Rate limit reached, waiting before retry")
                time.sleep(60)
            except tweepy.errors.TwitterServerError:
                logger.warning("Twitter server error, waiting before retry")
                time.sleep(30)
            except Exception as e:
                logger.error(f"Unexpected error in Twitter request: {str(e)}")
                raise

    def setup_api(self):
        """Initialize Twitter API v2 client"""
        try:
            # Check if credentials are present
            if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET, BEARER_TOKEN]):
                raise Exception("Missing required Twitter API credentials")

            logger.info("Initializing Twitter client...")
            self.client = tweepy.Client(
                consumer_key=API_KEY,
                consumer_secret=API_SECRET,
                access_token=ACCESS_TOKEN,
                access_token_secret=ACCESS_TOKEN_SECRET,
                bearer_token=BEARER_TOKEN,
                wait_on_rate_limit=True
            )

            # Test authentication
            me = self._make_twitter_request(lambda: self.client.get_me())
            if not me or not me.data:
                raise Exception("Could not verify credentials")

            logger.info(f"Authenticated as: @{me.data.username}")
            self.is_configured = True
            logger.info("✅ Twitter API initialized successfully")

        except Exception as e:
            logger.error(f"❌ Error during Twitter API setup: {e}")
            logger.exception("Full traceback:")
            self.is_configured = False
            self.client = None

    async def fetch_recent_tweets(self, force_refresh: bool = False, randomize: bool = True) -> List[Dict]:
        """Fetch tweets from cache or API if refresh needed"""
        if not self.is_configured:
            logger.warning("Twitter API not configured, returning cached tweets")
            return self.tweet_cache.get_all_tweets(randomize=randomize)

        if not force_refresh:
            cached_tweets = self.tweet_cache.get_all_tweets(randomize=randomize)
            if cached_tweets:
                logger.info("Returning cached tweets")
                return cached_tweets

        all_tweets = []
        try:
            import random
            usernames = TARGET_USERNAMES.copy()
            random.shuffle(usernames)

            for username in usernames:
                try:
                    logger.info(f"Fetching tweets for @{username}")

                    # Get user info
                    user = self._make_twitter_request(
                        lambda: self.client.get_user(
                            username=username,
                            user_fields=['profile_image_url', 'description']
                        )
                    )

                    if not user or not user.data:
                        logger.warning(f"Could not fetch user data for @{username}")
                        continue

                    user_id = user.data.id
                    user_info = user.data

                    # Get tweets
                    tweets = self._make_twitter_request(
                        lambda: self.client.get_users_tweets(
                            id=user_id,
                            max_results=10,
                            exclude=['retweets', 'replies'],
                            tweet_fields=['created_at', 'public_metrics', 'conversation_id']
                        )
                    )

                    if not tweets or not tweets.data:
                        logger.warning(f"No tweets found for @{username}")
                        continue

                    user_tweets = []
                    for tweet in tweets.data:
                        if getattr(tweet, 'in_reply_to_user_id', None):
                            continue

                        tweet_data = {
                            'id': tweet.id,
                            'username': username,
                            'display_name': user_info.name,
                            'profile_image': getattr(user_info, 'profile_image_url', None),
                            'text': tweet.text,
                            'created_at': tweet.created_at.isoformat(),
                            'likes': tweet.public_metrics['like_count'],
                            'retweets': tweet.public_metrics['retweet_count'],
                            'replies': tweet.public_metrics.get('reply_count', 0),
                            'url': f"https://twitter.com/{username}/status/{tweet.id}"
                        }
                        user_tweets.append(tweet_data)

                    self.tweet_cache.update_user_tweets(username, user_tweets)
                    all_tweets.extend(user_tweets)

                except Exception as e:
                    logger.error(f"Error processing tweets for @{username}: {str(e)}")
                    continue

            if all_tweets:
                logger.info(f"Successfully fetched {len(all_tweets)} tweets from {len(usernames)} users")
            else:
                logger.warning("No tweets fetched, falling back to cache")
                return self.tweet_cache.get_all_tweets(randomize=randomize)

            return self.tweet_cache.get_all_tweets(randomize=randomize)

        except Exception as e:
            logger.error(f"Error fetching tweets: {e}")
            logger.exception("Full traceback:")
            return self.tweet_cache.get_all_tweets(randomize=randomize)

    async def post_tweet(self, tweet_text: str) -> bool:
        """Post a standalone tweet"""
        if not self.is_configured:
            logger.warning("Twitter API not configured, skipping tweet")
            return False

        try:
            logger.info(f"Attempting to post tweet: {tweet_text}")
            response = self._make_twitter_request(
                lambda: self.client.create_tweet(text=tweet_text)
            )

            if response and hasattr(response, 'data') and isinstance(response.data, dict) and 'id' in response.data:
                tweet_id = response.data['id']
                me = self._make_twitter_request(lambda: self.client.get_me())
                username = me.data.username
                tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"
                logger.info(f"✅ Tweet posted successfully: {tweet_url}")
                return True
            else:
                logger.error("Failed to post tweet - invalid response")
                return False

        except tweepy.errors.Forbidden as e:
            logger.error(f"Permission error posting tweet: {str(e)}")
            logger.error("Check if your tokens have write permissions enabled")
            return False
        except tweepy.errors.TooManyRequests:
            logger.error("Rate limit exceeded when posting tweet")
            return False
        except Exception as e:
            logger.error(f"Error posting tweet: {str(e)}")
            logger.exception("Full traceback:")
            return False


# Initialize Twitter API singleton
twitter_api = TwitterAPI()