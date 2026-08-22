"""Makes `import app...` work when pytest is run from backend/.

Without this, pytest's rootdir handling means the test suite only imports
correctly if the package is installed. Keeping it here means `pytest` just
works from a fresh clone.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
