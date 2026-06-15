import os
import sys
import ctypes
import subprocess
import logging
from pathlib import Path

def run_as_admin():
    """Re-run the script with admin privileges if needed"""
    try:
        if ctypes.windll.shell32.IsUserAnAdmin():
            return True
            
        script = os.path.abspath(sys.argv[0])
        params = ' '.join([script] + sys.argv[1:])
        
        # Re-run the program with admin rights
        ctypes.windll.shell32.ShellExecuteW(
            None, 
            "runas", 
            sys.executable, 
            params, 
            None, 
            1
        )
        
        return False
    except Exception as e:
        print(f"Error elevating privileges: {e}")
        return False

class MitmCertInstaller:
    def __init__(self):
        self.cert_path = os.path.expanduser("~/.mitmproxy/mitmproxy-ca-cert.cer")
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('CertInstaller')

    def generate_certificate(self):
        """Generate the mitmproxy CA in-process if missing (no mitmdump subprocess).

        A frozen build ships no `mitmdump` executable, so we create the CA store
        directly via mitmproxy's API. CertStore.from_store writes
        mitmproxy-ca-cert.cer into the confdir (~/.mitmproxy by default).
        """
        if os.path.exists(self.cert_path):
            self.logger.info("Certificate already exists")
            return True
        self.logger.info("Certificate not found. Generating now...")
        try:
            from mitmproxy.certs import CertStore
            confdir = Path(self.cert_path).parent
            confdir.mkdir(parents=True, exist_ok=True)
            CertStore.from_store(confdir, "mitmproxy", 2048)
            if os.path.exists(self.cert_path):
                self.logger.info(f"Certificate generated successfully at: {self.cert_path}")
                return True
            self.logger.error("Certificate generation failed")
            return False
        except Exception as e:
            self.logger.error(f"Error generating certificate: {e}")
            return False

    def install_certificate(self):
        """Install mitmproxy certificate in Windows certificate store"""
        try:
            self.logger.info("Installing certificate...")
            result = subprocess.run(
                ['certutil', '-addstore', 'root', self.cert_path], 
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.logger.info("Certificate installed successfully!")
                self.logger.info("\nNext steps:")
                self.logger.info("1. Restart your browsers")
                self.logger.info("2. For TradingView Desktop, set system proxy to 127.0.0.1:8080")
                return True
            else:
                self.logger.error(f"Certificate installation failed: {result.stderr}")
                return False
                
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error installing certificate: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return False

def main():
    # Check for admin rights and re-run if needed
    if not ctypes.windll.shell32.IsUserAnAdmin():
        if run_as_admin():
            sys.exit(0)
        else:
            print("Failed to elevate privileges. Please run as administrator manually.")
            input("\nPress Enter to exit...")
            sys.exit(1)
    
    print("\nMitmproxy Certificate Installer")
    print("============================")
    
    installer = MitmCertInstaller()
    
    if installer.generate_certificate():
        installer.install_certificate()
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()