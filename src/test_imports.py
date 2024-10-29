print("Testing imports...\n")

def test_import(module_name):
    try:
        module = __import__(module_name)
        version = getattr(module, '__version__', 'unknown')
        print(f"✓ Successfully imported {module_name} (version: {version})")
        return True
    except ImportError as e:
        print(f"✗ Failed to import {module_name}: {e}")
        return False

print("Testing required packages:")
test_import('redis')
test_import('MetaTrader5')
test_import('sqlalchemy')
test_import('psycopg2')
test_import('dotenv')

print("\nTesting project modules:")
try:
    from src.workers import mt5_worker
    print("✓ Successfully imported mt5_worker")
except Exception as e:
    print(f"✗ Failed to import mt5_worker: {e}")

try:
    from src.services import mt5_service
    print("✓ Successfully imported mt5_service")
except Exception as e:
    print(f"✗ Failed to import mt5_service: {e}")