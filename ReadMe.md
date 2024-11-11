# TradingView to MT5 Trade Copier

Automatically copy trades from TradingView to MetaTrader 5 using a proxy server.

## Features
- Intercepts TradingView trades
- Copies trades to MT5 in real-time
- Supports market orders (buy/sell)
- Position tracking and management
- Trade status monitoring
- Persistent storage in PostgreSQL
- Real-time trade synchronization using Redis Pub/Sub
- Asynchronous operations
- Clean logging and error handling

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
.\venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Environment Setup

1. Make a copy of the `.env.template` file and name it `.env`:

   - `cp .env.template .env`
   - overwrite the values with your credentials
   - ⚠️ IMPORTANT: Never commit your `.env` file to version control!




2. Start services:

      `docker-compose up -d`

      Output should be similar to : 
      ```
      [+] Running 2/2
      ✔ Container tradingview_db       Running     0.0s
      ✔ Container tradingview_redis    Running     0.0s
      ```

3. Verify docker containers are running
    ```
    $ docker ps -a
      CONTAINER ID   IMAGE         COMMAND                  CREATED         STATUS                   PORTS                    NAMES
      73c4a6bc2c3c   postgres:16   "docker-entrypoint.s…"   5 minutes ago   Up 5 minutes (healthy)   0.0.0.0:5432->5432/tcp   tradingview_db
      ac6d86109537   redis:7       "docker-entrypoint.s…"   5 minutes ago   Up 5 minutes (healthy)   0.0.0.0:6379->6379/tcp   tradingview_redis
    ```

## Usage

The application provides a command-line interface for all operations:

### Core Commands
```bash
# Start the TradingView proxy server
python run.py proxy

# Start the MT5 worker
python run.py worker

# Update requirements.txt
python run.py update-reqs
```

### Symbol Management
```bash
# List all MT5 symbols
python run.py symbols

# Filter symbols
python run.py symbols --filter USD

# Show symbol management help
python run.py symbols-help
```

### Utility Commands
```bash
# Test database connection
python run.py test-db

# Clean Redis data
python run.py clean-redis

# Show all available commands
python run.py help
```

## Project Structure
```
src/
├── config/                     # Configuration
│   ├── constants.py           # Constants and URLs
│   ├── database.py           # Database config
│   ├── mt5_config.py         # MT5 credentials
│   └── mt5_symbol_config.py  # Symbol mappings
├── core/                      # Core functionality
│   ├── interceptor.py        # Proxy interceptor
│   └── trade_handler.py      # Trade processing
├── models/                    # Database models
│   └── database.py           # SQLAlchemy models
├── scripts/                   # Utility scripts
│   ├── check_db.py          # DB status check
│   ├── clean_redis.py       # Redis cleanup
│   ├── execution_stats.py   # Performance stats
│   ├── generate_requirements.py  # Deps manager
│   ├── init_db.py           # DB initialization
│   ├── manage_symbols.py    # Symbol management
│   ├── start_proxy.py       # Proxy starter
│   └── test_db.py          # DB connection test
├── services/                  # External services
│   ├── mt5_service.py       # MT5 operations
│   └── tradingview_service.py  # TV operations
├── utils/                     # Utilities
│   ├── database_handler.py  # DB operations
│   ├── queue_handler.py     # Redis operations
│   ├── ssl_handler.py       # SSL config
│   ├── symbol_mapper.py     # Symbol mapping
│   └── token_manager.py     # Auth management
├── workers/                   # Workers
│   └── mt5_worker.py        # MT5 trade executor
├── main.py                    # Main entry point
└── start_worker.py            # Worker entry
```

## Development

### Adding New Dependencies
```bash
pip install package-name
python run.py update-reqs
```

### Database Management
```bash
# Initialize database
python src/scripts/init_db.py

# Check database status
python src/scripts/check_db.py
```

### Symbol Management
```bash
# View all symbols
python src/scripts/manage_symbols.py --list

# Add mapping
python src/scripts/manage_symbols.py --add BTCUSD BTCUSD.r

# Update suffix
python src/scripts/manage_symbols.py --suffix .r
```

## System Requirements
- OS: Windows (primarily developed and tested), Linux/Mac (never tested, no gurantee it will work)
- RAM: 4GB minimum
- Disk Space: 1GB for installation
- Network: Stable internet connection
- Docker for PostgreSQL and Redis

## License

MIT License - see LICENSE file for details.