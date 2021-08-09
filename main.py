#!/usr/bin/env python

# Import
import sys
from argparse import ArgumentParser
import logging
from datto import DattoCheck
import config

from logging import StreamHandler, DEBUG, INFO, Formatter
from logging.handlers import RotatingFileHandler

def main():
    """Main"""

    __authors__ = ['Tommy Harris', 'Ryan Shoemaker']
    __date__ = 'September 8, 2019'
    __description__ = """Using the Datto API, get information on current status \
    of backups, screenshots, local verification, and device issues.

    To send the results as an email, provide the optional email parameters."""

    parser = ArgumentParser(description=__description__,
                            epilog='Developed by {} on \
                            {}'.format(", ".join(__authors__), __date__))

    # "Optional" arguments
    parser.add_argument('-v', '--verbose',
                        help='Print verbose output to stdout',
                        action='store_true')
    parser.add_argument('-u', '--unprotected-volumes', help='Include \
        any unprotected volumes in the final report',
        action='store_true')

    args = parser.parse_args()

    # Add rotating log
    logger = logging.getLogger("Datto Check")
    logger.setLevel(DEBUG)
    handler = RotatingFileHandler(config.LOG_FILE, maxBytes=30000, backupCount=3)
    handler.setLevel(INFO)
    formatter = Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # If verbose is set, add stdout logging handler
    if args.verbose:
        handler = StreamHandler(sys.stdout)
        handler.setLevel(DEBUG)
        formatter = Formatter('%(asctime)s - [%(levelname)s] %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.info('Starting Datto check')
    datto_check = DattoCheck(args.unprotected_volumes)
    datto_check.run()
    return 0

# Main
if __name__ == '__main__':
    sys.exit(main())
