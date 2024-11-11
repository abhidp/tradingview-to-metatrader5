#!/usr/bin/env python
# run.py

import argparse
import subprocess
import sys
import signal
from pathlib import Path

class Runner:
    def run_proxy(self):
        """Start the TradingView proxy server."""
        try:
            subprocess.run(
                [sys.executable, "src/scripts/start_proxy.py"],
                check=True
            )
        except KeyboardInterrupt:
            pass
        except subprocess.CalledProcessError:
            sys.exit(1)

    def run_worker(self):
        """Start the MT5 worker."""
        try:
            subprocess.run(
                [sys.executable, "src/start_worker.py"],
                check=True
            )
        except KeyboardInterrupt:
            pass
        except subprocess.CalledProcessError:
            sys.exit(1)

    def update_requirements(self):
        """Update requirements.txt."""
        subprocess.run(["python", "src/scripts/generate_requirements.py"])

    def list_symbols(self):
        """List MT5 symbols."""
        subprocess.run(["python", "src/scripts/manage_symbols.py", "--mt5-symbols"])

    def manage_symbols(self):
        """Show symbol management help."""
        print("\nSymbol Management Commands:")
        print("---------------------------")
        print("List symbols:   python run.py symbols")
        print("Add mapping:    python run.py symbols-add BTCUSD BTCUSD.r")
        print("Remove mapping: python run.py symbols-remove BTCUSD")
        print("Update suffix:  python run.py symbols-suffix .r")

    def test_db(self):
        """Test database connection."""
        subprocess.run(["python", "src/scripts/test_db.py"])

    def clean_redis(self):
        """Clean Redis data."""
        subprocess.run(["python", "src/scripts/clean_redis.py"])

    def show_help(self):
        """Show help message."""
        print("\nAvailable commands:")
        print("-" * 50)
        commands = {
            "proxy": "Start the TradingView proxy server",
            "worker": "Start the MT5 worker",
            "update-reqs": "Update requirements.txt",
            "symbols": "List all MT5 symbols",
            "symbols-help": "Show symbol management commands",
            "test-db": "Test database connection",
            "clean-redis": "Clean Redis data",
            "help": "Show this help message"
        }
        for cmd, desc in commands.items():
            print(f"python run.py {cmd:<15} - {desc}")

def main():
    parser = argparse.ArgumentParser(description="TradingView Copier CLI")
    parser.add_argument('command', nargs='?', default='help',
                       help="Command to execute")
    parser.add_argument('args', nargs=argparse.REMAINDER,
                       help="Additional arguments for the command")

    args = parser.parse_args()
    runner = Runner()

    # Command mapping
    commands = {
        'proxy': runner.run_proxy,
        'worker': runner.run_worker,
        'update-reqs': runner.update_requirements,
        'symbols': runner.list_symbols,
        'symbols-help': runner.manage_symbols,
        'test-db': runner.test_db,
        'clean-redis': runner.clean_redis,
        'help': runner.show_help
    }

    if args.command in commands:
        try:
            commands[args.command]()
        except KeyboardInterrupt:
            print("\nOperation cancelled by user")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        print(f"Unknown command: {args.command}")
        runner.show_help()
        sys.exit(1)

if __name__ == "__main__":
    main()