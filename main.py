#!/usr/bin/env python

# Import
import sys
import argparse
import logging
from datto import DattoCheck
import config

from logging import StreamHandler, DEBUG, INFO, Formatter
from logging.handlers import RotatingFileHandler

def main():
    """Main entry.

    Parse command line arguments.
    Basic checks on CLI input.
    Initialize and run."""
    __authors__ = ['Tommy Harris', 'Ryan Shoemaker']
    __date__ = 'September 8, 2019'
    __description__ = """Using the Datto API, get information on current status \
    of backups, screenshots, local verification, and device issues.

    To send the results as an email, provide the optional email parameters."""

    parser = argparse.ArgumentParser(description=__description__,
                                     epilog='Developed by {} on \
                                     {}'.format(", ".join(__authors__), __date__))

    # "Optional" arguments
    parser.add_argument('-v', '--verbose',
                        help='Print verbose output to stdout',
                        action='store_true')
    parser.add_argument('--unprotected-volumes', '-u', help='Include \
        any unprotected volumes in the final report',
        action='store_true')

    args = parser.parse_args()

    # args sanity check
    if args.send_email:
        if not args.email_from or not args.email_to or not args.mx_endpoint:
            raise InvalidEmailSettings("You must have at least a \
            sender, recipient, and MX endpoint.")

    # Add rotating log
    logger = logging.getLogger("Datto Check")
    logger.setLevel(DEBUG)
    handler = RotatingFileHandler(LOG_FILE, maxBytes=30000, backupCount=3)
    handler.setLevel(INFO)
    formatter = Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # If verbose is set, add stdout logging handler
    if args.verbose:
        handler = StreamHandler(sys.stdout)
        handler.setLevel(DEBUG)
        formatter = Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    datto_check = DattoCheck(args)
    datto_check.run()
    return 0

# Main
if __name__ == '__main__':
    sys.exit(main())
