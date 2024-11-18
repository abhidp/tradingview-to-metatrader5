import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)

from src.utils.token_manager import GLOBAL_TOKEN_MANAGER

logger = logging.getLogger('InstrumentSync')

class InstrumentSynchronizer:
    def __init__(self):
        load_dotenv()
        self.token_manager = GLOBAL_TOKEN_MANAGER
        self.config_path = Path(__file__).parent.parent.parent / 'data' / 'instruments.json'
        self.broker_url = f"https://{os.getenv('TV_BROKER_URL')}/accounts/{os.getenv('TV_ACCOUNT_ID')}"

    async def fetch_tv_instruments(self) -> dict:
        """Fetch instruments from TradingView API."""
        try:
            token = self.token_manager.get_token()
            if not token:
                print("❌ No auth token available")
                return {}

            url = f"{self.broker_url}/instruments?locale=en"
            headers = {
                'accept': 'application/json',
                'authorization': f'{token}'
            }

            print(f"🔄 Fetching instruments from: {url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ Received {len(data.get('d', []))} instruments")
                        return self._process_tv_response(data)
                    else:
                        print(f"❌ API request failed: {response.status}")
                        response_text = await response.text()
                        print(f"Response: {response_text}")
                        print(f"Headers sent: {headers}")
                        return {}
        except Exception as e:
            print(f"❌ Error fetching instruments: {e}")
            return {}

    def _process_tv_response(self, data: dict) -> dict:
        """Process TradingView API response into our format."""
        categories = {
            'instruments': {
                'description': 'All trading instruments',
                'pairs': []
            },
            'custom': {
                'description': 'User-defined instruments',
                'pairs': []
            }
        }

        print("\nProcessing instruments:")
        for instrument in data.get('d', []):
            name = instrument['name']
            instrument_type = instrument.get('type', '').lower()
            pip_size = float(instrument.get('pipSize', 0))
            
            # Format pip_size to avoid scientific notation
            pip_size_str = f"{pip_size:.10f}".rstrip('0').rstrip('.')
            
            print(f"  - {name} : pip_size {pip_size_str}")
            
            categories['instruments']['pairs'].append({
                'name': name,
                'pip_size': pip_size_str
            })

        # Sort pairs by name for readability
        categories['instruments']['pairs'].sort(key=lambda x: x['name'])
        return categories

    async def sync_instruments(self):
        """Sync instruments from TV to local config."""
        print("\n🔄 Syncing instruments from TradingView...")
        
        tv_instruments = await self.fetch_tv_instruments()
        if not tv_instruments:
            return

        # Load existing config to preserve custom pairs
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    existing_config = json.load(f)
                    if 'custom' in existing_config:
                        tv_instruments['custom'] = existing_config['custom']
                        print("✅ Preserved custom instrument settings")
            except Exception as e:
                print(f"⚠️  Warning: Could not load existing config: {e}")

        # Save updated config
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(tv_instruments, f, indent=4)
                print(f"✅ Instruments synchronized successfully to {self.config_path}")
                
            # Print summary
            print("\nSynchronized instruments:")
            for category, data in tv_instruments.items():
                if isinstance(data['pairs'], list):
                    count = len(data['pairs'])
                    print(f"  {category}: {count} instruments")
                
        except Exception as e:
            print(f"❌ Error saving configuration: {e}")

def main():
    syncer = InstrumentSynchronizer()
    asyncio.run(syncer.sync_instruments())

if __name__ == "__main__":
    main()
