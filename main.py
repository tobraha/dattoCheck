#!/usr/bin/env python

# Import
import sys
import argparse
import datto
from config import *

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

    # Add positional arguments
    parser.add_argument('AUTH_USER', help='Datto API User (REST API Public Key)')
    parser.add_argument('AUTH_PASS', help='Datto API Password (REST API Secret Key')
    parser.add_argument('XML_API_KEY', help='Datto XML API Key')

    # "Optional" arguments
    parser.add_argument('-v', '--verbose',
                        help='Print verbose output to stdout',
                        action='store_true')
    parser.add_argument('--send-email',
                        help='Set this flag to send an email.  \
                        Below parameters required if set',
                        action='store_true')
    parser.add_argument('--email-to',
                        help='Email address to send message to. \
                        Use more than once for multiple recipients.',
                        action='append')
    parser.add_argument('--email-cc',
                        help='(OPTIONAL) Email address to CC. \
                        Use more than once for multiple recipients.',
                        action='append')
    parser.add_argument('--email-from', help='Email address to send message from')
    parser.add_argument('--email-pw', help='Password to use for authentication')
    parser.add_argument('--mx-endpoint', help='MX Endpoint of where to send the email')
    parser.add_argument('--smtp-port',
                        help='TCP port to use when sending the email; default=25',
                        choices=['25', '465', '587'],
                        default='25')
    parser.add_argument('--starttls', help='Specify whether to use \
    STARTTLS or not', action='store_true')

    args = parser.parse_args()

    # args sanity check
    if args.send_email:
        if not args.email_from or not args.email_to or not args.mx_endpoint:
            raise InvalidEmailSettings("You must have at least a \
            sender, recipient, and MX endpoint.")

    datto_check = datto.DattoCheck(args)
    datto_check.run()
    return 0

# Main
if __name__ == '__main__':
    sys.exit(main())
