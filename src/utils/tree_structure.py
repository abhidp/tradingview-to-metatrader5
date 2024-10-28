import os

def print_tree(start_path, skip_dirs=None, prefix=""):
    if skip_dirs is None:
        skip_dirs = []
    
    items = sorted(os.listdir(start_path))
    for index, item in enumerate(items):
        item_path = os.path.join(start_path, item)
        is_last = index == len(items) - 1
        connector = "└── " if is_last else "├── "

        # Skip any directories specified
        if os.path.basename(item_path) in skip_dirs:
            continue

        print(prefix + connector + item)
        
        # Recursively print directory structure for folders
        if os.path.isdir(item_path):
            extension = "    " if is_last else "│   "
            print_tree(item_path, skip_dirs=skip_dirs, prefix=prefix + extension)

# Run the function with the path to your project and the directories you want to skip
print_tree(".", skip_dirs=["venv", ".git"])
