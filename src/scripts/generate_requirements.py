# scripts/generate_requirements.py

import subprocess
import pkg_resources
import re
from pathlib import Path

def get_project_root():
    """Get project root directory."""
    # Get the directory two levels up from this script
    # scripts/generate_requirements.py -> src/scripts -> project_root
    return Path(__file__).resolve().parent.parent.parent

def get_installed_packages():
    """Get list of installed packages with versions."""
    return {pkg.key: pkg.version for pkg in pkg_resources.working_set}

def get_core_packages():
    """Define core packages that must be included."""
    return {
        # Proxy & Networking
        'mitmproxy',
        'requests',
        'aiohttp',
        
        # Database
        'psycopg2-binary',
        'sqlalchemy',
        'redis',
        
        # Trading
        'MetaTrader5',
        'numpy',  # Required for MT5
        
        # Utilities
        'python-dotenv',
        'tabulate',
        
        # Additional utilities your project uses
        'urllib3',
    }

def get_imported_packages():
    """Scan project files for imports."""
    project_root = get_project_root()
    imports = set()
    
    # Packages to ignore (standard library modules)
    stdlib_modules = {'os', 'sys', 'time', 'datetime', 'logging', 'json', 
                     'pathlib', 'typing', 'contextlib', 'functools', 'asyncio'}
    
    # Scan all Python files
    for py_file in project_root.rglob('*.py'):
        if 'venv' in str(py_file) or '.git' in str(py_file):
            continue
            
        with open(py_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Find imports
        import_lines = re.findall(r'^(?:from|import)\s+([\w\.]+)', content, re.MULTILINE)
        for imp in import_lines:
            # Get base package name
            base_pkg = imp.split('.')[0]
            if base_pkg not in stdlib_modules:
                imports.add(base_pkg)
    
    return imports

def get_dependency_tree():
    """Get dependency tree using pip-tree."""
    try:
        result = subprocess.run(['pip-tree'], capture_output=True, text=True)
        return result.stdout
    except FileNotFoundError:
        return None

def generate_requirements():
    """Generate requirements.txt with actually used packages."""
    installed_packages = get_installed_packages()
    imported_packages = get_imported_packages()
    core_packages = get_core_packages()
    
    # Combine all required packages
    required_packages = imported_packages.union(core_packages)
    
    # Generate requirements.txt in project root
    requirements_path = get_project_root() / 'requirements.txt'
    with open(requirements_path, 'w') as f:
        f.write("# Generated requirements.txt\n\n")
        
        # Write core dependencies
        f.write("# Core dependencies\n")
        for category, packages in {
            "# Proxy & Networking": ['mitmproxy', 'requests', 'aiohttp'],
            "# Database": ['psycopg2-binary', 'sqlalchemy', 'redis'],
            "# Trading": ['MetaTrader5', 'numpy'],
            "# Utilities": ['python-dotenv', 'tabulate', 'urllib3']
        }.items():
            f.write(f"\n{category}\n")
            for package in sorted(packages):
                if package in installed_packages:
                    f.write(f"{package}=={installed_packages[package]}\n")
        
        # Write development dependencies
        f.write("\n# Development dependencies\n")
        dev_packages = [
            'pytest',
            'pylint',
            'black',
            'autopep8'
        ]
        for package in dev_packages:
            if package in installed_packages:
                f.write(f"# {package}=={installed_packages[package]}\n")

    print(f"✅ Generated requirements.txt")
    print(f"📍 Location: {requirements_path}")
    
    # Show the contents of the generated file
    print("\nGenerated requirements.txt contents:")
    print("-" * 50)
    with open(requirements_path, 'r') as f:
        print(f.read())
    
    # Print dependency tree if available
    tree = get_dependency_tree()
    if tree:
        print("\nDependency Tree:")
        print(tree)
    else:
        print("\nTip: Install pip-tree to see dependency relationships:")
        print("pip install pip-tree")

if __name__ == "__main__":
    generate_requirements()