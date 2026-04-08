"""Worker entry point — executes jobs dispatched by the scheduler.

Populated in task 1.5.
"""

import logging

from app.common.logging import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    logger.info("Worker started (no jobs registered yet)")


if __name__ == "__main__":
    main()
