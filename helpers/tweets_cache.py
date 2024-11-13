# tweets_cache.py
import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Optional
from core.config import logger


class TweetCache:
    def __init__(self, cache_file: str = 'tweets_cache.json'):
        self.cache_file = cache_file
        self.cache: Dict[str, List[Dict]] = {}
        self._load_cache()

    def _load_cache(self):
        """Load cached tweets from file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
                logger.info(f"Loaded {len(self.cache)} users' tweets from cache")
            except json.JSONDecodeError:
                self.cache = {}
                logger.error("Error loading cache, initializing empty cache")
        else:
            self.cache = {}

    def _save_cache(self):
        """Save tweets to cache file"""
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)
        logger.info("Cache saved to file")

    def update_user_tweets(self, username: str, new_tweets: List[Dict]):
        """Update cached tweets for a user, maintaining max 10 latest tweets"""
        if not username in self.cache:
            self.cache[username] = []

        # Convert existing tweet IDs to set for quick lookup
        existing_ids = {tweet['id'] for tweet in self.cache[username]}

        # Add only new tweets
        for tweet in new_tweets:
            if tweet['id'] not in existing_ids:
                self.cache[username].append(tweet)

        # Sort by created_at and keep only the 10 most recent
        self.cache[username] = sorted(
            self.cache[username],
            key=lambda x: x['created_at'],
            reverse=True
        )[:10]

        self._save_cache()

    def get_all_tweets(self, randomize: bool = True) -> List[Dict]:
        """Get all cached tweets across all users"""
        all_tweets = []
        for username in self.cache:
            all_tweets.extend(self.cache[username])

        if randomize:
            # First filter out any tweets used in the last hour
            current_time = datetime.now(timezone.utc)
            recent_tweets = [
                tweet for tweet in all_tweets
                if (current_time - datetime.fromisoformat(
                    tweet['created_at'].replace('Z', '+00:00'))).total_seconds() < 3600
            ]

            # If we have enough recent tweets, randomly select from them
            # Otherwise, fall back to all tweets
            if len(recent_tweets) >= 5:
                all_tweets = recent_tweets

            # Shuffle the tweets instead of sorting by engagement
            import random
            random.shuffle(all_tweets)
            return all_tweets
        else:
            # If randomize is False, sort by engagement as before
            return sorted(
                all_tweets,
                key=lambda x: x['likes'] + x['retweets'],
                reverse=True
            )

    def clear_cache(self):
        """Clear the entire cache"""
        self.cache = {}
        self._save_cache()