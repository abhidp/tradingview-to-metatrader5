import logging
import subprocess
import sys
import time
import warnings
from datetime import datetime

# Suppress PyQt5 deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import psutil
from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import (QApplication, QLabel, QMenu, QSystemTrayIcon,
                             QVBoxLayout, QWidget)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('process_monitor.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('ProcessMonitor')

class ProcessMonitor(QObject):
    status_changed = pyqtSignal(str, bool)  # Process name, is_running

    def __init__(self):
        super().__init__()
        self.processes = {
            'Proxy': {
                'name': 'mitmdump',  # Changed from mitmproxy to mitmdump
                'running': False
            },
            'Worker': {
                'name': 'python',  # Process name to look for
                'cmd_pattern': 'mt5_worker',  # Pattern to match in command line
                'running': False
            }
        }

    def check_process(self, process_name: str, cmd_pattern: str = None) -> bool:
        """Check if a process is running."""
        try:
            for proc in psutil.process_iter(['name', 'cmdline']):
                try:
                    proc_name = proc.info['name'].lower()
                    
                    # For Python processes, get the full command line
                    if proc_name.startswith('python') and cmd_pattern:
                        try:
                            cmdline = proc.cmdline()
                            cmdline_str = ' '.join(cmdline).lower()
                            logger.debug(f"Python process cmdline: {cmdline_str}")
                            
                            # Check if the command line contains our pattern
                            if cmd_pattern.lower() in cmdline_str:
                                logger.info(f"Found worker process: PID {proc.pid}")
                                logger.debug(f"Complete command line: {cmdline_str}")
                                return True
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                            
                    # For non-Python processes (like mitmdump)
                    elif proc_name.startswith(process_name.lower()):
                        logger.info(f"Found matching process: {proc_name}")
                        return True
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return False
        except Exception as e:
            logger.error(f"Error checking process: {e}")
            return False

    def check_all_processes(self):
        """Check status of all monitored processes."""
        for proc_key, proc_info in self.processes.items():
            try:
                current_status = self.check_process(
                    proc_info['name'],
                    proc_info.get('cmd_pattern')
                )
                
                # Only emit if status changed
                if current_status != proc_info['running']:
                    self.processes[proc_key]['running'] = current_status
                    self.status_changed.emit(proc_key, current_status)
                    
                    # Log status change
                    status_str = "running" if current_status else "stopped"
                    logger.info(f"{proc_key} process is {status_str}")
            except Exception as e:
                logger.error(f"Error checking {proc_key}: {e}")

class SystemTrayApp(QWidget):
    def __init__(self):
        super().__init__()
        self.monitor = ProcessMonitor()
        self.initUI()

    def initUI(self):
        # Create system tray icon
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip('Process Monitor')

        # Create tray menu
        self.menu = QMenu()
        self.status_menu = self.menu.addMenu('Process Status')
        
        # Add status items for each process
        self.status_items = {}
        for proc_name in self.monitor.processes.keys():
            self.status_items[proc_name] = self.status_menu.addAction(
                f'{proc_name}: Checking...'
            )
            self.status_items[proc_name].setEnabled(False)

        self.menu.addSeparator()
        exitAction = self.menu.addAction('Exit')
        exitAction.triggered.connect(self.close)

        self.tray.setContextMenu(self.menu)
        self.update_icon()
        self.tray.show()

        # Connect monitor signals
        self.monitor.status_changed.connect(self.update_process_status)

        # Start monitoring timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.monitor.check_all_processes)
        self.timer.start(5000)  # Check every 5 seconds

        # Initial check
        self.monitor.check_all_processes()

    def update_process_status(self, proc_name: str, is_running: bool):
        """Update the status display for a process."""
        status = "Running" if is_running else "Stopped"
        color = "green" if is_running else "red"
        self.status_items[proc_name].setText(
            f'{proc_name}: <font color="{color}">{status}</font>'
        )
        self.update_icon()
        logger.info(f"Updated status for {proc_name}: {status}")

    def update_icon(self):
        """Update the tray icon based on process statuses."""
        all_running = all(proc['running'] for proc in self.monitor.processes.values())
        any_running = any(proc['running'] for proc in self.monitor.processes.values())
        
        if all_running:
            color = QColor(0, 255, 0)  # Green
        elif any_running:
            color = QColor(255, 255, 0)  # Yellow
        else:
            color = QColor(255, 0, 0)  # Red
            
        # Create colored icon
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, 12, 12)
        painter.end()
        
        self.tray.setIcon(QIcon(pixmap))
        
        # Log current status
        status = "all running" if all_running else "some running" if any_running else "none running"
        logger.info(f"Updated icon status: {status}")

    def closeEvent(self, event):
        """Handle application closure."""
        self.tray.hide()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    try:
        ex = SystemTrayApp()
        sys.exit(app.exec_())
    except Exception as e:
        logger.error(f"Application error: {e}")