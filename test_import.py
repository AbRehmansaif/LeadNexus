import os
import sys

# Add the current directory to sys.path
sys.path.append(os.getcwd())

try:
    import seo
    print("SEO module found")
    print(f"Path: {seo.__file__}")
except ImportError as e:
    print(f"ImportError: {e}")
