import os
from contextlib import asynccontextmanager
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, BackgroundTasks
from agents.agent import generate_tweet, fetch_and_generate_summaries, load_archive, save_archive
from core.config import SUMMARIES_FILE, TWEETS_ARCHIVE, ANTHROPIC_API_KEY
from core.config import logger
from helpers.gecko_terminal import gecko_terminal_api
from helpers.twitter_helpers import twitter_api
from helpers.content_tracker import ContentTracker

# Initialize scheduler
scheduler = AsyncIOScheduler()


async def update_tweet_cache():
    """Update tweet cache every hour"""
    logger.info("🔄 Updating tweet cache...")
    try:
        tweets = await twitter_api.fetch_recent_tweets(force_refresh=True)
        if tweets:
            logger.info(f"✅ Tweet cache updated with {len(tweets)} tweets")
    except Exception as e:
        logger.error(f"Error updating tweet cache: {e}")


async def generate_and_post_tweet():
    """Generate and post tweet based on current market context"""
    try:
        logger.info("\n=== Starting Tweet Generation Process ===")
        content_tracker = ContentTracker()

        # Load and filter articles
        summaries_archive = load_archive(SUMMARIES_FILE)
        available_articles = [
            article for article in summaries_archive['items']
            if not content_tracker.is_article_processed(article)
        ]

        if not available_articles:
            logger.info("No new articles available for tweeting")
            return

        logger.info(f"Found {len(available_articles)} unprocessed articles")

        # Get market context with deduplication
        trending_pools = await gecko_terminal_api.get_trending_pools()
        filtered_pools = []

        for pool in trending_pools:
            base_token = pool['base_token']
            quote_token = pool['quote_token']

            if (content_tracker.is_token_recently_mentioned(base_token) or
                    content_tracker.is_token_recently_mentioned(quote_token)):
                continue

            filtered_pools.append(pool)

        logger.info(f"Using {len(filtered_pools[:5])} trending pools for context")

        # Get social context
        tweets = await twitter_api.fetch_recent_tweets()
        logger.info(f"Retrieved {len(tweets)} tweets for context")

        # Generate tweet
        logger.info("\n=== Generating Tweet ===")
        result = await generate_tweet(
            articles=available_articles[:5],
            tweets=tweets,
            trending_pools=filtered_pools[:5],
            api_key=ANTHROPIC_API_KEY
        )

        if not result:
            logger.error("Failed to generate tweet content")
            return

        tweet_text, reasoning = result

        # Log the generated content
        logger.info("\n=== Generated Content ===")
        logger.info("Generated Tweet:")
        logger.info("-" * 50)
        logger.info(tweet_text)
        logger.info("-" * 50)
        logger.info("\nReasoning:")
        logger.info("-" * 50)
        logger.info(reasoning)
        logger.info("-" * 50)

        # Check for similar tweets
        if content_tracker.is_tweet_similar(tweet_text):
            logger.warning("Generated tweet too similar to recent tweets, skipping")
            return

        # Prepare tweet data
        tweet_data = {
            'timestamp': datetime.now().isoformat(),
            'tweet': tweet_text,
            'reasoning': reasoning,
            'posted_to_twitter': False,  # Default to False
            'source_articles': [
                {
                    'title': article['title'],
                    'link': article['link'],
                    'summary': article['summary']
                } for article in available_articles[:5]
            ],
            'market_context': [
                {
                    'name': pool['name'],
                    'base_token': pool['base_token'],
                    'quote_token': pool['quote_token'],
                    'price_change_24h': float(pool['price_changes']['h24'] or 0),
                    'volume_24h': float(pool['volumes']['h24'] or 0),
                } for pool in filtered_pools[:5]
            ]
        }

        # Try to post to Twitter
        logger.info("\n=== Attempting to Post Tweet ===")
        success = await twitter_api.post_tweet(tweet_text)

        # Update posted status if successful
        if success:
            tweet_data['posted_to_twitter'] = True
            logger.info("✅ Tweet successfully posted to Twitter")

            # Track content if posted successfully
            for article in available_articles[:5]:
                content_tracker.track_article(article)

            for pool in filtered_pools[:5]:
                content_tracker.track_token_mention(pool['base_token'])
                content_tracker.track_token_mention(pool['quote_token'])

            content_tracker.track_generated_tweet(tweet_text, available_articles[:5])
        else:
            logger.warning("❌ Tweet not posted to Twitter (API not configured)")

        # Save to archive regardless of posting status
        tweets_archive = load_archive(TWEETS_ARCHIVE)
        tweets_archive['tweets'].append(tweet_data)
        save_archive(tweets_archive, TWEETS_ARCHIVE)
        logger.info("✅ Tweet content saved to archive")

        return tweet_data

    except Exception as e:
        logger.error("❌ Error in tweet generation process")
        logger.error(f"Error details: {str(e)}")
        logger.exception("Full traceback:")
        return None


async def initialize_files():
    """Initialize necessary JSON files if they don't exist"""
    if not os.path.exists(SUMMARIES_FILE):
        save_archive({'processed_urls': [], 'items': []}, SUMMARIES_FILE)
    if not os.path.exists(TWEETS_ARCHIVE):
        save_archive({'processed_urls': [], 'tweets': []}, TWEETS_ARCHIVE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Initialize files
        await initialize_files()

        # Initial data fetch only
        logger.info("Performing initial data fetch...")
        await fetch_and_generate_summaries()
        await update_tweet_cache()

        # Schedule jobs
        logger.info("Setting up scheduled tasks...")

        # Article summaries regeneration - every 12 hours
        scheduler.add_job(
            fetch_and_generate_summaries,
            CronTrigger(hour='*/12'),
            id='summaries_refresh'
        )

        # Tweet cache update - every hour at minute 25
        scheduler.add_job(
            update_tweet_cache,
            CronTrigger(minute=25),  # Run 5 minutes before tweet generation
            id='cache_refresh'
        )

        # Tweet generation - every hour at minute 30
        # scheduler.add_job(
        #     generate_and_post_tweet,
        #     CronTrigger(minute=30),  # Fixed time instead of random
        #     id='tweet_generation'
        # )

        scheduler.start()
        logger.info("Scheduler started with jobs:")
        logger.info("- Article regeneration: Every 12 hours")
        logger.info("- Cache refresh: Every hour at minute 25")
        logger.info("- Tweet generation: Every hour at minute 30")

        yield

    finally:
        if scheduler.running:
            scheduler.shutdown()
            logger.info("Scheduler shut down")


# Create FastAPI app
app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    next_tweet_job = scheduler.get_job('next_tweet')
    next_run = next_tweet_job.next_run_time if next_tweet_job else None

    return {
        "status": "running",
        "next_tweet_scheduled": next_run.isoformat() if next_run else None,
        "uptime": "active"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "scheduler_running": scheduler.running,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/trigger-summary")
async def trigger_summary(background_tasks: BackgroundTasks):
    """Endpoint to manually trigger article fetching and summarization"""
    background_tasks.add_task(fetch_and_generate_summaries)
    return {"status": "Summary generation initiated"}


@app.post("/trigger-tweet")
async def trigger_tweet(background_tasks: BackgroundTasks):
    """Endpoint to manually trigger tweet generation and posting"""
    background_tasks.add_task(generate_and_post_tweet)
    return {"status": "Tweet generation initiated"}


@app.get("/stats")
async def get_stats():
    """Get bot statistics"""
    summaries_archive = load_archive(SUMMARIES_FILE)
    tweets_archive = load_archive(TWEETS_ARCHIVE)
    next_tweet_job = scheduler.get_job('next_tweet')

    return {
        "total_articles": len(summaries_archive.get('items', [])),
        "total_tweets_posted": len(tweets_archive.get('tweets', [])),
        "next_tweet_scheduled": next_tweet_job.next_run_time.isoformat() if next_tweet_job else None,
        "scheduler_running": scheduler.running
    }


def run_server():
    """Run the FastAPI server"""
    import uvicorn
    logger.info("Starting FastAPI server...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )


if __name__ == "__main__":
    run_server()
