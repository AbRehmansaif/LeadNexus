import os
import sys

# Add project root to path
sys.path.append(os.path.abspath('.'))

try:
    import admintask
    print("admintask OK")
except ImportError as e:
    print(f"admintask Error: {e}")

try:
    from admintask import views
    print("admintask.views OK")
except Exception as e:
    print(f"admintask.views Error: {e}")
    import traceback
    traceback.print_exc()

try:
    from admintask.utils import alerts
    print("admintask.utils.alerts OK")
except Exception as e:
    print(f"admintask.utils.alerts Error: {e}")
    import traceback
    traceback.print_exc()
