# URL Configuration
BASE_URL = 'icmarkets.tv.ctrader.com/accounts/40807470/orders'

# Required trade fields
REQUIRED_TRADE_FIELDS = {'instrument', 'side', 'qty'}

# Console messages
STARTUP_MESSAGE = "\n🚀 Trade capture proxy server started"
MONITORING_MESSAGE = "Monitoring for trade executions...\n"
TRADE_EXECUTED_MESSAGE = "\n📊 Trade Executed:"

# Trade field labels
TRADE_FIELDS = {
    'instrument': 'Instrument',
    'side': 'Side',
    'qty': 'Quantity',
    'type': 'Type'
}

# File operations
SEPARATOR_LINE = "-" * 40