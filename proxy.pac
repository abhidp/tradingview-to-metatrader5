function FindProxyForURL(url, host) {
    // Use proxy only for TradingView and ICMarkets
    if (shExpMatch(host, "*.tradingview.com") ||
        shExpMatch(host, "*.icmarkets.tv.ctrader.com")) {
        return "PROXY 127.0.0.1:8080";
    }
    // Direct connection for all other traffic
    return "DIRECT";
}