import hashlib
from datetime import datetime, timedelta
from typing import Dict, List
from core.config import logger
from helpers.file_utils import load_archive, save_archive


class ContentTracker:
    CATEGORIES = {
        'price': ['price', 'surge', '$', 'rally', 'market', 'ath', 'high', 'low', 'dump', 'pump'],
        'innovation': ['launch', 'update', 'protocol', 'tech', 'scaling', 'develop', 'release'],
        'adoption': ['adopt', 'user', 'integration', 'partnership', 'mainstream', 'institutional'],
        'regulation': ['regulation', 'law', 'compliance', 'legal', 'license', 'govern'],
        'security': ['hack', 'scam', 'security', 'protect', 'risk', 'vulnerability'],
        'defi': ['defi', 'yield', 'stake', 'liquidity', 'amm', 'swap'],
        'infrastructure': ['layer2', 'scaling', 'network', 'chain', 'bridge', 'protocol'],
        'social': ['community', 'governance', 'dao', 'vote', 'proposal']
    }

    def __init__(self, archive_file='content_tracking.json'):
        self.archive_file = archive_file
        self.tracking_data = load_archive(archive_file)
        if not self.tracking_data:
            self.tracking_data = {
                'article_hashes': {},  # Store article content hashes
                'token_mentions': {},  # Track token mentions
                'generated_tweets': {},  # Track generated tweet content
                'topic_clusters': {}  # Group similar topics
            }

    def _generate_content_hash(self, content: str) -> str:
        """Generate a hash of the content for comparison"""
        return hashlib.md5(content.lower().encode()).hexdigest()

    def is_article_processed(self, article: Dict) -> bool:
        """Check if article content has been processed before"""
        content_hash = self._generate_content_hash(article['title'] + article.get('summary', ''))

        if content_hash in self.tracking_data['article_hashes']:
            stored_time = datetime.fromisoformat(
                self.tracking_data['article_hashes'][content_hash]['timestamp']
            )
            # Only consider articles processed in the last 48 hours
            if datetime.now() - stored_time < timedelta(hours=48):
                return True
        return False

    def _categorize_content(self, text: str) -> set:
        """Categorize content into multiple possible categories"""
        text_lower = text.lower()
        categories = set()

        for category, keywords in self.CATEGORIES.items():
            if any(keyword in text_lower for keyword in keywords):
                categories.add(category)

        return categories

    def is_topic_overused(self, article: Dict) -> bool:
        """Check if a topic category has been overused recently"""
        article_categories = self._categorize_content(
            article['title'] + ' ' + article.get('summary', '')
        )

        recent_cutoff = datetime.now() - timedelta(hours=24)
        category_counts = {cat: 0 for cat in self.CATEGORIES.keys()}

        # Count recent category usage
        for tweet in self.tracking_data['generated_tweets'].values():
            tweet_time = datetime.fromisoformat(tweet['timestamp'])
            if tweet_time > recent_cutoff:
                tweet_categories = self._categorize_content(tweet['text'])
                for cat in tweet_categories:
                    category_counts[cat] += 1

        # Check if any of the article's categories are overused
        return any(category_counts[cat] >= 2 for cat in article_categories)

    def get_fresh_categories(self) -> set:
        """Get categories that haven't been used recently"""
        recent_cutoff = datetime.now() - timedelta(hours=24)
        used_categories = set()

        for tweet in self.tracking_data['generated_tweets'].values():
            if datetime.fromisoformat(tweet['timestamp']) > recent_cutoff:
                used_categories.update(self._categorize_content(tweet['text']))

        return set(self.CATEGORIES.keys()) - used_categories

    def is_token_recently_mentioned(self, token: str, hours: int = 24) -> bool:
        """Check if a token/coin has been recently mentioned"""
        if token in self.tracking_data['token_mentions']:
            last_mention = datetime.fromisoformat(
                self.tracking_data['token_mentions'][token]['last_mention']
            )
            return datetime.now() - last_mention < timedelta(hours=hours)
        return False

    def is_tweet_similar(self, tweet_text: str, similarity_threshold: float = 0.7) -> bool:
        """Check if proposed tweet is too similar to recent tweets"""
        tweet_tokens = set(tweet_text.lower().split())

        # Check against recent tweets (last 48 hours)
        recent_cutoff = datetime.now() - timedelta(hours=48)

        for stored_tweet in self.tracking_data['generated_tweets'].values():
            if datetime.fromisoformat(stored_tweet['timestamp']) < recent_cutoff:
                continue

            stored_tokens = set(stored_tweet['text'].lower().split())
            similarity = len(tweet_tokens & stored_tokens) / len(tweet_tokens | stored_tokens)

            if similarity > similarity_threshold:
                logger.info(f"Tweet similar to existing tweet (similarity: {similarity:.2f})")
                return True

        return False

    def track_article(self, article: Dict) -> None:
        """Record processed article"""
        content_hash = self._generate_content_hash(article['title'] + article.get('summary', ''))
        self.tracking_data['article_hashes'][content_hash] = {
            'title': article['title'],
            'url': article['link'],
            'summary': article.get('summary', ''),
            'timestamp': datetime.now().isoformat()
        }
        self._save_tracking_data()

    def track_token_mention(self, token: str) -> None:
        """Record token mention"""
        self.tracking_data['token_mentions'][token] = {
            'last_mention': datetime.now().isoformat(),
            'mention_count': self.tracking_data['token_mentions'].get(token, {}).get('mention_count', 0) + 1
        }
        self._save_tracking_data()

    def track_generated_tweet(self, tweet_text: str, source_articles: List[Dict]) -> None:
        """Record generated tweet"""
        tweet_hash = self._generate_content_hash(tweet_text)
        self.tracking_data['generated_tweets'][tweet_hash] = {
            'text': tweet_text,
            'timestamp': datetime.now().isoformat(),
            'sources': [{
                'title': art['title'],
                'url': art['link'],
                'summary': art.get('summary', '')
            } for art in source_articles]
        }
        self._save_tracking_data()

    def _save_tracking_data(self) -> None:
        """Save tracking data to file"""
        try:
            save_archive(self.tracking_data, self.archive_file)
            logger.info("Successfully saved tracking data")
        except Exception as e:
            logger.error(f"Error saving tracking data: {e}")

    def cleanup_old_data(self, days: int = 7) -> None:
        """Remove tracking data older than specified days"""
        cutoff = datetime.now() - timedelta(days=days)

        self.tracking_data['article_hashes'] = {
            k: v for k, v in self.tracking_data['article_hashes'].items()
            if datetime.fromisoformat(v['timestamp']) > cutoff
        }

        self.tracking_data['token_mentions'] = {
            k: v for k, v in self.tracking_data['token_mentions'].items()
            if datetime.fromisoformat(v['last_mention']) > cutoff
        }

        self.tracking_data['generated_tweets'] = {
            k: v for k, v in self.tracking_data['generated_tweets'].items()
            if datetime.fromisoformat(v['timestamp']) > cutoff
        }

        self._save_tracking_data()
        logger.info(f"Cleaned up tracking data older than {days} days")