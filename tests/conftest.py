"""Keep test-created Natbirzha apps public unless a test enables the gate explicitly."""

import os

os.environ.setdefault("NATBIRZHA_ADMIN_ONLY_ACCESS", "false")
