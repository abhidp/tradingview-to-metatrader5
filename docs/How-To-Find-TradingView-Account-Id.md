Your TradingView `ACCOUNT_ID` is NOT the same as your Broker provided username, userId, TradingView login email, broker login email, cTraderId, MT4/MT5 id or any other ids.
There are high chances that you have never seen or heard of this id. This id can be found in the network calls of your browser after you are logging in to TradingView and inspecting the Network tab.
Below are the steps on how to find it:

1. Login to TradingView as usual using your TradingView email and password
2. Once logged in, connect to your broker via the Trading Panel
3. Open the Network Tab in your browser. If you dont know how to open the network tab, refer https://developer.chrome.com/docs/devtools/network/
4. In the Network Tab, click on any of the network calls to view its details. The `TV_BROKER_URL` and `TV_ACCOUNT_ID` is present in the url
![TV_ACCOUNT_ID](TV_ACCOUNT_ID.png)
5. Once you have found the values, enter it in your .env file like so:
    ```
    TV_BROKER_URL=tradingview-api-client-demo.fusionmarkets.com
    TV_ACCOUNT_ID=27269
    ```