import psutil
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ProcessDebug')

def find_python_processes():
    """Find all Python processes and their command lines."""
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            proc_name = proc.info['name'].lower()
            cmdline = proc.info['cmdline']
            
            if proc_name.startswith('python'):
                logger.info("-" * 50)
                logger.info(f"Process Name: {proc_name}")
                logger.info(f"Command Line: {cmdline}")
                logger.info(f"PID: {proc.pid}")
                try:
                    logger.info(f"Working Directory: {proc.cwd()}")
                except:
                    pass
                logger.info("-" * 50)
                
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

if __name__ == '__main__':
    print("Scanning for Python processes...")
    find_python_processes()