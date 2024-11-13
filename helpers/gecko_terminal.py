import requests
from typing import Dict, List
from core.config import logger, GECKO_TERMINAL_API, MARKET_METRICS


class GeckoTerminalAPI:
    def __init__(self):
        self.base_url = GECKO_TERMINAL_API

    async def get_trending_pools(self) -> List[Dict]:
        """Fetch and parse trending pools data with enhanced filtering"""
        try:
            response = requests.get(f"{self.base_url}/networks/trending_pools")
            response.raise_for_status()
            data = response.json()

            trending_pools = []
            for pool in data.get('data', []):
                attrs = pool.get('attributes', {})

                # Check minimum volume and liquidity requirements
                volume_24h = float(attrs.get('volume_usd', {}).get('h24', 0) or 0)
                liquidity = float(attrs.get('reserve_in_usd', 0) or 0)

                if (volume_24h < MARKET_METRICS['min_volume_24h'] or
                        liquidity < MARKET_METRICS['min_liquidity']):
                    continue

                # Get token names from relationships
                base_token = \
                pool.get('relationships', {}).get('base_token', {}).get('data', {}).get('id', '').split('_')[-1]
                quote_token = \
                pool.get('relationships', {}).get('quote_token', {}).get('data', {}).get('id', '').split('_')[-1]

                # Get price changes for all timeframes
                price_changes = {}
                for timeframe in MARKET_METRICS['price_timeframes']:
                    price_changes[timeframe] = attrs.get('price_change_percentage', {}).get(timeframe)

                # Get volume data for all timeframes
                volumes = {}
                for timeframe in MARKET_METRICS['volume_timeframes']:
                    volumes[timeframe] = attrs.get('volume_usd', {}).get(timeframe)

                # Get transaction data for all timeframes
                transactions = {}
                for timeframe in MARKET_METRICS['transaction_timeframes']:
                    tx_data = attrs.get('transactions', {}).get(timeframe, {})
                    transactions[timeframe] = {
                        'buys': tx_data.get('buys', 0),
                        'sells': tx_data.get('sells', 0),
                        'buyers': tx_data.get('buyers', 0),
                        'sellers': tx_data.get('sellers', 0)
                    }

                pool_data = {
                    'name': attrs.get('name'),
                    'base_token': base_token,
                    'quote_token': quote_token,
                    'price_changes': price_changes,
                    'volumes': volumes,
                    'market_cap': attrs.get('market_cap_usd'),
                    'fdv': attrs.get('fdv_usd'),
                    'liquidity': attrs.get('reserve_in_usd'),
                    'transactions': transactions,
                    'network': pool.get('relationships', {}).get('network', {}).get('data', {}).get('id'),
                    'dex': pool.get('relationships', {}).get('dex', {}).get('data', {}).get('id'),
                    'created_at': attrs.get('pool_created_at'),
                    'base_token_price_usd': attrs.get('base_token_price_usd'),
                    'quote_token_price_usd': attrs.get('quote_token_price_usd')
                }

                # Calculate buy/sell ratio and pressure metrics
                h24_tx = transactions.get('h24', {})
                if h24_tx.get('sells', 0) > 0:
                    pool_data['buy_sell_ratio'] = h24_tx.get('buys', 0) / h24_tx.get('sells', 0)
                else:
                    pool_data['buy_sell_ratio'] = float('inf') if h24_tx.get('buys', 0) > 0 else 1.0

                trending_pools.append(pool_data)

            # Sort by 24h volume
            trending_pools.sort(key=lambda x: float(x['volumes'].get('h24', 0) or 0), reverse=True)

            logger.info(f"Fetched and filtered {len(trending_pools)} trending pools")
            return trending_pools

        except Exception as e:
            logger.error(f"Error fetching trending pools: {e}")
            logger.exception("Full traceback:")
            return []


# Initialize global instance
gecko_terminal_api = GeckoTerminalAPI()