import os
import pytest
from unittest.mock import patch

@pytest.fixture(autouse=True)
def mock_elemm_home(tmp_path):
    """
    Automatically redirects ~/.elemm to a temporary directory for all tests.
    This ensures that the test suite does not use or alter the user's global 
    configuration, which could contain strict security policies like zero-trust mode.
    """
    original_expanduser = os.path.expanduser
    
    # Create the mocked .elemm directory in the temporary pytest path
    mocked_home = tmp_path / ".elemm"
    mocked_home.mkdir(parents=True, exist_ok=True)

    def mock_expanduser(path):
        if path.startswith("~/.elemm"):
            return path.replace("~/.elemm", str(mocked_home))
        return original_expanduser(path)

    with patch('os.path.expanduser', side_effect=mock_expanduser):
        yield
