#!/usr/bin/env

# Import
import sys
import argparse

def main():
    __authors__ = ['Tommy Harris', 'Ryan Shoemaker']
    __date__ = 'September 8, 2019'
    __description__ = '''Using the Datto API, get information on current status \
    of backups, screenshots, local verification, and device issues.\n

    To send the results as an email, provide the optional email parameters.'''

    parser = argparse.ArgumentParser(description=__description__,
                                epilog='Developed by {} on {}'.format(", ".join(__authors__), __date__ ))

    # Add positional arguments
    parser.add_argument('AUTH_USER', help='Datto API User (REST API Public Key)')
    parser.add_argument('AUTH_PASS', help='Datto API Password (REST API Secret Key')
    parser.add_argument('XML_API_KEY', help='Datto XML API Key')

    # "Optional" arguments
    parser.add_argument('--send-email',
                        help='Set this flag to send an email.  Below parameters required if set',
                        action='store_true')
    parser.add_argument('--email-to',
                        help='Email address to send message to. Use more than once for multiple recipients.',
                        action='append',
                        required=True)
    parser.add_argument('--email-cc',
                        help='(OPTIONAL) Email address to CC. Use more than once for multiple recipients.',
                        action='append')
    parser.add_argument('--email-from', help='Email address to send message from', required=True)
    parser.add_argument('--email-pw', help='Password to use for authentication')
    parser.add_argument('--mx-endpoint', help='MX Endpoint of where to send the email', required=True)
    parser.add_argument('--smtp-port',
                        help='TCP port to use when sending the email; default=25',
                        type=int, 
                        choices=['25', '587'], 
                        default='25')
    parser.add_argument('--starttls', help='Specify whether to use STARTTLS or not', action='store_true')
    parser.add_argument('-v', '--verbose', help='Print verbose output to stdout', action='store_true')

    args = parser.parse_args()

    from datto import DattoCheck

    dattoCheck = DattoCheck(args)
    dattoCheck.run()
    return 0

# Main
if __name__ == '__main__':
    sys.exit(main())