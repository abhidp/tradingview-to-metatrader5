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
tradingview-trade-capture/
├── src/
│   └── proxy_server.py
├── logs/
│   └── trades/
├── venv/
├── requirements.txt
├── start_proxy.bat
├── README.md
└── .gitignore
```

## License

MIT License - see LICENSE file for details.