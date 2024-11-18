import asyncio
import json
from pathlib import Path

import aiohttp


class InstrumentSynchronizer:
    def __init__(self):
        self.config_path = Path(__file__).parent.parent.parent / 'data' / 'instruments.json'

    async def fetch_instruments(self, token: str, broker_url: str) -> dict:
        """Fetch instruments from TradingView."""
        url = f"{broker_url}/instruments?locale=en"
        headers = {
            'accept': 'application/json',
            'authorization': f'{token}',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://www.tradingview.com',
            'referer': 'https://www.tradingview.com/'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                return None

    async def sync_instruments(self) -> None:
        """Sync instruments from TradingView to local config."""
        from src.utils.token_manager import GLOBAL_TOKEN_MANAGER
        
        try:
            token = GLOBAL_TOKEN_MANAGER.get_token()
            broker_url = f"https://{os.getenv('TV_BROKER_URL')}/accounts/{os.getenv('TV_ACCOUNT_ID')}"
            
            if not token:
                print("❌ No auth token available")
                return

            print("🔄 Fetching instruments from TradingView...")
            data = await self.fetch_instruments(token, broker_url)
            
            if not data:
                print("❌ Failed to fetch instruments")
                return

            instruments = {
                'instruments': {
                    'description': 'All trading instruments',
                    'pairs': []
                },
                'custom': {
                    'description': 'User-defined instruments',
                    'pairs': []
                }
            }

            for instrument in data.get('d', []):
                name = instrument['name']
                pip_size = float(instrument.get('pipSize', 0))
                pip_size_str = f"{pip_size:.10f}".rstrip('0').rstrip('.')
                
                instruments['instruments']['pairs'].append({
                    'name': name,
                    'pip_size': pip_size_str
                })

            # Preserve custom pairs if file exists
            if self.config_path.exists():
                try:
                    with open(self.config_path, 'r') as f:
                        existing = json.load(f)
                        if 'custom' in existing:
                            instruments['custom'] = existing['custom']
                except Exception:
                    pass

            # Sort pairs by name
            instruments['instruments']['pairs'].sort(key=lambda x: x['name'])

            # Save configuration
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(instruments, f, indent=4)

            print(f"✅ Synced {len(instruments['instruments']['pairs'])} instruments")

        except Exception as e:
            print(f"❌ Error syncing instruments: {e}")