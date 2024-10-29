import sys
print(f"Python version: {sys.version}")

try:
    import numpy as np
    print(f"NumPy version: {np.__version__}")
except Exception as e:
    print(f"Failed to import NumPy: {e}")

try:
    import MetaTrader5 as mt5
    print(f"MetaTrader5 version: {mt5.__version__}")
    
    # Initialize MT5
    if mt5.initialize():
        print("✓ MT5 initialized successfully")
        print(f"MT5 terminal info: {mt5.terminal_info()}")
        print(f"MT5 version: {mt5.version()}")
    else:
        print(f"✗ Failed to initialize MT5: {mt5.last_error()}")
    
    # Clean up
    mt5.shutdown()
    
except Exception as e:
    print(f"Failed to import/initialize MT5: {e}")