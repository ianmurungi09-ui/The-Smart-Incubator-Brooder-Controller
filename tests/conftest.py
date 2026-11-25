"""Test setup: use a throw-away database so tests never touch real data."""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="brooder-tests-")
os.environ["BROODER_DB"] = os.path.join(_TMP, "test.db")   # must be set before webapp.app is imported
