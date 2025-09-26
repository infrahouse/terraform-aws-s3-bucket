import logging

from infrahouse_core.logging import setup_logging

DEFAULT_PROGRESS_INTERVAL = 10
TEST_TIMEOUT = 3600

LOG = logging.getLogger(__name__)
TERRAFORM_ROOT_DIR = "test_data"

setup_logging(LOG, debug=True)
