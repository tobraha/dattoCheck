# Configurations
#
# all runtime settings and configurations are defined in this file

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
CHECKIN_LIMIT = 60 * 20                  # threshold for device offline time
STORAGE_PCT_THRESHOLD = 95               # threshold for local storage; in percent
LAST_BACKUP_THRESHOLD = 60 * 60 * 12     # threshold for failed backup time
LAST_OFFSITE_THRESHOLD = 60 * 60 * 72    # threshold for last successful off-site
LAST_SCREENSHOT_THRESHOLD = 60 * 60 * 48 # threshold for last screenshot taken
ACTIONABLE_THRESHOLD = 60 * 60 * 24 * 7  # threshold for actionable alerts; one week

# Logs - check if /var/log is writable. Otherwise, output to currnent directory
if os.access('/var/log', os.W_OK):
	LOG_DIR = Path("/var/log")
else:
	LOG_DIR = Path(os.getcwd())
LOG_FILE = (LOG_DIR / 'datto_check.log')
