import tweepy
import logging
import os
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Twitter API Credentials
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_KEY_SECRET')
BEARER_TOKEN = os.getenv('BEARER_TOKEN')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.getenv('ACCESS_TOKEN_SECRET')


def test_twitter_post():
    try:
        # Initialize client
        logger.info("Initializing Twitter client...")
        client = tweepy.Client(
            consumer_key=API_KEY,
            consumer_secret=API_SECRET,
            access_token=ACCESS_TOKEN,
            access_token_secret=ACCESS_TOKEN_SECRET,
            bearer_token=BEARER_TOKEN
        )

        # Test authentication
        me = client.get_me()
        logger.info(f"Authenticated as: @{me.data.username}")

        # Test tweet
        test_tweet = "This is a test tweet from my Twitter API test script 🚀"
        response = client.create_tweet(text=test_tweet)

        if response and hasattr(response, 'data') and isinstance(response.data, dict) and 'id' in response.data:
            tweet_id = response.data['id']
            tweet_url = f"https://twitter.com/{me.data.username}/status/{tweet_id}"
            logger.info(f"✅ Tweet posted successfully!")
            logger.info(f"Tweet URL: {tweet_url}")
            return True
        else:
            logger.error("Failed to post tweet - invalid response")
            return False

    except tweepy.errors.Forbidden as e:
        logger.error(f"Permission error: {str(e)}")
        logger.error("Check if your tokens have write permissions enabled")
        return False
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        logger.exception("Full traceback:")
        return False


if __name__ == "__main__":
    logger.info("Starting Twitter API test...")
    test_twitter_post()
