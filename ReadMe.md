# TradingView to MT5 Trade Copier

Automatically copy trades from TradingView to MetaTrader 5 using a proxy server.

## Features
- Intercepts TradingView trades
- Copies trades to MT5 in real-time
- Supports market orders (buy/sell)
- Position tracking and management
- Trade status monitoring
- Persistent storage in PostgreSQL
- Message queueing with Redis

## Prerequisites

  - Python 3.11
  - Docker Desktop
  - MetaTrader 5 Terminal

## Installation

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/tradingview-trade-capture.git
cd tradingview-trade-capture
```

2. Create and activate virtual environment:
```bash
python -m venv venv
venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Environment Setup

1. Copy the environment template:
```bash
cp .env.template .env
```

2. Update `.env` with your credentials:
  ```ini
  # Database
  DB_HOST=localhost
  DB_PORT=5432
  DB_NAME=tradingview
  DB_USER=tvuser
  DB_PASSWORD=tvpassword

  # Redis
  REDIS_HOST=localhost
  REDIS_PORT=6379

  # MT5
  MT5_ACCOUNT=your_account_number
  MT5_PASSWORD=your_mt5_password
  MT5_SERVER=ICMarkets-Demo
  ```

⚠️ IMPORTANT: Never commit your `.env` file to version control!

3. Start services
  `docker-compose up -d`## Usage

1. Start the proxy server:
   ```powershell
   .\start_proxy.ps1
   ```

2. Start the MT5 worker:
   ```powershell
   .\start_worker.ps1
   ```

3. Configure your system proxy to `127.0.0.1:8080`

4. Symbol Mappings
    The system uses a mapping file to convert between TradingView and MT5 symbols. 
    A template is provided in `data/symbol_mappings.template.json`.

    To initialize your mappings:
    1. Copy template: `copy data\symbol_mappings.template.json data\symbol_mappings.json`
    2. Run the management script: `python src/scripts/manage_symbols.py -r`

5. Place trades in TradingView - they will automatically be copied to MT5.

## Project Structure
```
tradingview-trade-capture/
├── logs/                         # Log files (git ignored)
│   └── trades/                   # Trade execution logs
├── src/                          # Source code
│   ├── config/                   # Configuration
│   │   ├── constants.py          # Constants and URL patterns
│   │   ├── database.py           # Database configuration
│   │   └── mt5_config.py         # MT5 credentials
│   ├── core/                     # Core functionality
│   │   ├── interceptor.py        # Proxy interceptor
│   │   └── trade_handler.py      # Trade processing
│   ├── models/                   # Database models
│   │   └── database.py           # SQLAlchemy models
│   ├── services/                 # External services
│   │   └── mt5_service.py        # MT5 operations
│   ├── utils/                    # Utilities
│   │   ├── database_handler.py   # Database operations
│   │   ├── queue_handler.py      # Redis operations
│   │   └── symbol_mapper.py      # Symbol mapping
│   ├── workers/                  # Workers
│   │   └── mt5_worker.py         # MT5 trade executor
│   ├── main.py                   # Proxy entry point
│   └── start_worker.py           # Worker entry point
├── .env                          # Environment variables (git ignored)
├── .env.template                 # Environment template
├── .gitignore                    # Git ignore rules
├── docker-compose.yml            # Docker services config
├── init.sql                      # Database initialization
├── LICENSE                       # Project license
├── requirements.txt              # Python dependencies
├── start_proxy.ps1               # Proxy starter script
└── start_worker.ps1              # Worker starter script
```


## Maintainence

- View execution statistics:
`python src/scripts/execution_stats.py`

- Check database status:
`python src/scripts/check_db.py`

- Clean Redis queues:
`python src/scripts/clean_redis.py`

## License

MIT License - see LICENSE file for details.