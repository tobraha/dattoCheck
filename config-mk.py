# Configurations
#
# all runtime settings and configurations are defined in this file
# NOTE
# You MUST copy 'config-mk.py' to 'config.py' and edit that.
# The 'config-mk.py' file will not be read by the program.

import os
from pathlib import Path

# API URIs
API_BASE_URI = 'https://api.datto.com/v1/bcdr/device'
XML_API_BASE_URI = 'https://portal.dattobackup.com/external/api/xml/status'

# API authentication
AUTH_USER = ''
AUTH_PASS = ''
AUTH_XML  = ''

# Email configs
EMAIL_FROM  = ''
EMAIL_TO    = []
EMAIL_CC    = []
EMAIL_LOGIN = EMAIL_FROM
EMAIL_PW    = ''
EMAIL_MX    = ''
EMAIL_PORT  = 25
EMAIL_SSL   = True


# Error/Alert threshold settings
CHECKIN_LIMIT = 60 * 20                  # device offline time; 20 minutes
STORAGE_PCT_THRESHOLD = 95               # local storage; in percent
LAST_BACKUP_THRESHOLD = 60 * 60 * 12     # failed backup time; 12 hrs
LAST_OFFSITE_THRESHOLD = 60 * 60 * 72    # last successful off-site; 72 hrs
LAST_SCREENSHOT_THRESHOLD = 60 * 60 * 48 # last screenshot taken; 48 hrs
ACTIONABLE_THRESHOLD = 60 * 60 * 24 * 7  # actionable alerts; 7 days

# Log file location
if os.name != 'nt':
    if os.access('/var/log', os.W_OK):
        # default
        LOG_DIR = Path("/var/log")
    elif os.access(os.getcwd(), os.W_OK):
        # fallback
        LOG_DIR = Path(os.getcwd())
    else:
        # last resort
        LOG_DIR = Path('/tmp')
else:
    # for Windows, use current directory
    LOG_DIR = Path(os.getcwd())

LOG_FILE = (LOG_DIR / 'datto_check.log')
