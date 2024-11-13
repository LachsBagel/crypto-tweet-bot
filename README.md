# Crypto News Tweet Generator Bot

An automated system that generates witty pro-crypto tweets based on news articles (via CoinTelegraph), 
market activity (via GeckoTerminal), and crypto Twitter discussions. 
Uses Claude for news summarization and contextual tweet generation.

## Prerequisites

- Python 3.10+
- Anthropic API key
- Twitter API with Read & Write enabled for OAuth 1.0a / 2.0

## Installation

1. Clone the repository
2. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your credentials:
   ```env
   ANTHROPIC_API_KEY=your_anthropic_key
   BEARER_TOKEN=your_twitter_bearer_token
   API_KEY=your_twitter_api_key
   API_KEY_SECRET=your_twitter_api_secret
   ACCESS_TOKEN=your_twitter_access_token
   ACCESS_TOKEN_SECRET=your_twitter_access_token_secret
   ```
4. Configure `tweets_config.json` with example tweets
5. Run the service in tmux:
   ```bash
   tmux new -s cryptobot
   python main.py
   # Detach with Ctrl+B, then D
   ```
7. Run `curl -X POST http://localhost:8000/trigger-tweet` to initiate the tweet generation process. 
You can even run a cron job to run this command each hour or so.

## System Flow

The system automatically:
1. Fetches and summarizes crypto news articles every 12 hours
2. Updates tweet cache from monitored accounts every hour
3. Fetches trending pools data from GeckoTerminal
4. Generates and posts a witty pro-crypto tweet when you hit `POST http://localhost:8000/trigger-tweet`

Each tweet is generated considering:
- Latest crypto news summaries
- Recent tweets from influential crypto accounts
- Current market activity and trends
- Historical example tweets

## Configuration

Create `tweets_config.json` with example tweets:
```json
{
  "pro_crypto": [
    "Example tweet showing optimistic crypto perspective",
    "Example tweet highlighting innovation in the space",
    "Example tweet about market dynamics"
  ]
}
```

## Data Sources

- **News**: CoinTelegraph RSS feed
- **Market Data**: GeckoTerminal API (trending pools, volume, transactions)
- **Social Context**: Monitored crypto Twitter accounts
- **Example Style**: Curated pro-crypto tweets from `tweets_config.json`

## Monitoring

Access system status via HTTP endpoints:
- Health check: `http://localhost:8000/health`
- Statistics: `http://localhost:8000/stats`
- Manual article fetch: `POST http://localhost:8000/fetch-articles`
- Manual tweet generation: `POST http://localhost:8000/trigger-tweet`

The stats endpoint provides:
- Total articles processed
- Total tweets generated
- Next scheduled tweet time
- System status

## Project Structure

The project consists of several key components:
- `main.py`: FastAPI app, scheduling, and endpoints
- `agent.py`: Article processing and tweet generation
- `config.py`: System configuration and prompts
- `twitter_helpers.py`: Twitter API integration
- `tweets_cache.py`: Tweet caching system
- `gecko_terminal.py`: Market data integration

## Logs

The system maintains detailed logs of:
- Article fetching and summarization
- Tweet generation and posting
- Market data updates
- Cache management
- System status and errors

Logs use standard Python logging with timestamps and levels for easy monitoring.
