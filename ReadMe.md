# TradingView Trade Capture

A proxy server that captures trade executions from TradingView to ICMarkets.

## Features

- Captures trade executions in real-time
- Logs trade details including instrument, side, quantity, and type
- Stores trades in a structured JSON format
- Minimal console output - only shows actual trade executions

## Prerequisites

- Python 3.8+
- mitmproxy
- Windows OS (for batch script)

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
```env
# MT5 settings
MT5_ACCOUNT=12345678
MT5_PASSWORD=your_actual_password
MT5_SERVER=ICMarkets-Live
```

⚠️ IMPORTANT: Never commit your `.env` file to version control!


## Usage

1. Start the proxy server:
```bash
start_proxy.bat
```

2. Configure your TradingView to use the proxy:
   - Set proxy address to: localhost
   - Set proxy port to: 8080

3. Execute trades on TradingView as normal. The proxy will capture and log all trade executions.

4. Trade data will be stored in: `logs/trades/trades_YYYYMMDD_HHMMSS.json`

## Output Format

Each trade is logged in JSON format with the following structure:
```json
{
  "timestamp": "2024-10-28T01:32:13.974520",
  "request_data": {
    "currentAsk": "67559.49",
    "currentBid": "67544.49",
    "instrument": "BTCUSD",
    "qty": "0.03",
    "side": "buy",
    "type": "market"
  },
  "response": {
    "s": "ok",
    "d": {
      "orderId": "764986466"
    }
  }
}
```

## Project Structure
```
tradingview-trade-capture/      # Root directory
├── logs/                       # Log files directory (git ignored)
│   └── trades/                 # Trade execution logs
│
├── src/                        # Source code
│   ├── config/                 # Configuration
│   │   ├── constants.py        # Constants and URL patterns
│   │   ├── database.py         # Database configuration
│   │   └── mt5_config.py       # MT5 credentials and settings
│   │
│   ├── core/                   # Core functionality
│   │   ├── interceptor.py      # Proxy interceptor
│   │   └── trade_handler.py    # Trade processing logic
│   │
│   ├── models/                 # Database models
│   │   ├── database.py         # SQLAlchemy models
│   │   └── trade.py            # Trade entity definition
│   │
│   ├── scripts/                # Utility scripts
│   │   ├── check_db.py         # Database status check
│   │   └── reset_db.py         # Database initialization
│   │
│   ├── services/               # External services
│   │   ├── mt5_service.py      # MT5 connection
│   │   └── trade_executor.py   # Trade execution logic
│   │
│   ├── utils/                  # Utilities
│   │   ├── database_handler.py # Database operations
│   │   ├── queue_handler.py    # Redis queue operations
│   │   └── symbol_mapper.py    # Symbol mapping TV->MT5
│   │
│   ├── workers/                # Background workers
│   │   └── mt5_worker.py       # MT5 trade execution worker
│   │
│   ├── main.py                 # Proxy server entry point
│   └── start_worker.py         # Worker entry point
│
├── .env                        # Environment variables (git ignored)
├── .env.template               # Environment variables template
├── .gitignore                  # Git ignore rules
├── docker-compose.yml          # Docker services configuration
├── init.sql                    # Database initialization script
├── LICENSE                     # Project license
├── ReadMe.md                   # Project documentation
├── requirements.txt            # Python dependencies
├── start_proxy.ps1             # Proxy server startup script
└── start_worker.ps1            # Worker startup script
```

## License

MIT License - see LICENSE file for details.