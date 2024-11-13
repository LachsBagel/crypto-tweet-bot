import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-3-opus-20240229"
CLAUDE_MAX_TOKENS = 2048

TARGET_USERNAMES = [
    'MorpheusAIs',
    'ErikVoorhees',
    'pmarca',
    'CryptoGodJohn',
    'cdixon'
]

# API Endpoints
RSS_FEED = "https://cointelegraph.com/rss"
GECKO_TERMINAL_API = "https://api.geckoterminal.com/api/v2"

# API Keys
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
BEARER_TOKEN = os.getenv('BEARER_TOKEN')
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_KEY_SECRET')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.getenv('ACCESS_TOKEN_SECRET')

# Storage Files
SUMMARIES_FILE = 'article_summaries.json'
TWEETS_ARCHIVE = 'generated_tweets.json'
TWEETS_CONFIG = 'tweets_config.json'
TWEET_CACHE_FILE = 'tweets_cache.json'

MAIN_AGENT_INSTRUCTIONS = (
    "I'm providing you with comprehensive crypto market context including:"
    "\n- Recent news summaries"
    "\n- Tweets from prominent crypto accounts"
    "\n- Trending DEX pools and market activity"
    "\n\nAnalyze this context and:"
    "\n1. Identify key narratives from:"
    "\n- Latest news developments"
    "\n- Market activity and trends"
    "\n- Crypto Twitter discussions"
    "\n- Notable price movements"
    "\n- Trading volume and liquidity changes"
    "\n\n2. Generate a witty, engaging tweet that:"
    "\n- Is optimistic about crypto's potential"
    "\n- References current market activity or news"
    "\n- Keeps under 280 characters"
    "\n- Uses crypto Twitter slang naturally"
    "\n- Feels authentic to crypto culture"
    "\n- Makes clever observations"
    "\n- Avoids emojis and hashtags"
    "\n- Creates engagement through insight"
)

MAIN_AGENT_INSTRUCTIONS_PART_TWO = (
    "First explain your reasoning for the tweet, considering recent market events and sentiment, "
    "prefixed with 'REASONING: '.\n"
    "Then on a new line provide ONLY the tweet text prefixed with 'TWEET: '."
)

TONE_PROMPT = """You are an insightful crypto analyst focused on technological progress, adoption stories, and 
infrastructure development. While you're optimistic about crypto's future, you prioritize discussing concrete 
developments and real-world impact over price movements. Your tweets should:

1. Focus on specific developments rather than general market commentary
2. Highlight technological achievements and milestones
3. Share adoption stories and real-world applications
4. Discuss infrastructure improvements and scaling solutions
5. Analyze regulatory developments and their implications

Avoid:
- Starting tweets with price commentary
- Making price predictions or market calls
- Using overused phrases like 'flirting with...' or 'while tradfi...'
- Mixing multiple themes in one tweet
- Generic market observations

Instead:
- Tell specific stories about technology and adoption
- Use concrete details and numbers
- Focus on user impact and real-world applications
- Share infrastructure and scaling developments
- Discuss governance and community achievements"""

# Market Data Config
MARKET_METRICS = {
    'price_timeframes': ['m5', 'h1', 'h6', 'h24'],
    'volume_timeframes': ['m5', 'h1', 'h6', 'h24'],
    'transaction_timeframes': ['m5', 'm15', 'm30', 'h1', 'h24'],
    'min_volume_24h': 100000,  # Minimum 24h volume to consider a pool relevant
    'min_liquidity': 50000,  # Minimum liquidity to consider a pool relevant
}
