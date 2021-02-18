#!/usr/bin/python3

import requests
import sys
import datetime
import argparse
import traceback
import logging
from retry import retry
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
from logging.handlers import RotatingFileHandler

__authors__ = ['Tommy Harris', 'Ryan Shoemaker']
__date__ = 'September 8, 2019'
__description__ = '''Using the Datto API, get information on current status of backups, screenshots, local verification,\
and device issues.\n

To send the results as an email, provide the optional email parameters.'''

parser = argparse.ArgumentParser(description=__description__,
                                 epilog='Developed by {} on {}'.format(", ".join(__authors__), __date__ ))

# Add positional arguments
parser.add_argument('AUTH_USER', help='Datto API User (REST API Public Key)')
parser.add_argument('AUTH_PASS', help='Datto API Password (REST API Secret Key')
parser.add_argument('XML_API_KEY', help='Datto XML API Key')

# Optional arguments
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
parser.add_argument('--smtp-port', help='TCP port to use when sending the email', type=int, choices=['25', '587'], default='25')
parser.add_argument('--starttls', help='Specify whether to use STARTTLS or not', action='store_true')
parser.add_argument('--verbose', '-v', help='Print verbose output to stdout', action='store_true')

# Parsing and using the arguments
args = parser.parse_args()

# Global Variables
API_BASE_URI = 'https://api.datto.com/v1/bcdr/device'
XML_API_URI = 'https://portal.dattobackup.com/external/api/xml/status/{0}'.format(args.XML_API_KEY)
AUTH_USER = args.AUTH_USER
AUTH_PASS = args.AUTH_PASS

# Add rotating log
logger = logging.getLogger("Datto Check")
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler("/var/log/datto_check.log", maxBytes=30000, backupCount=3)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# If verbose is set, add stdout logging handler
if args.verbose:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

## Set this to True to send the report email:
SEND_EMAIL = False
if args.send_email:
    SEND_EMAIL = True

## Error/Alert threshold settings
CHECKIN_LIMIT = 60 * 20                  # threshold for device offline time
STORAGE_PCT_THRESHOLD = 95               # threshold for local storage; in percent
LAST_BACKUP_THRESHOLD = 60 * 60 * 12     # threshold for failed backup time
LAST_OFFSITE_THRESHOLD = 60 * 60 * 72    # threshold for last successful off-site
LAST_SCREENSHOT_THRESHOLD = 60 * 60 * 48 # threshold for last screenshot taken
ACTIONABLE_THRESHOLD = 60 * 60 * 24 * 7  # threshold for actionable alerts; one week

## Define errors
class Error(Exception):
    """Base class for errors/exceptions"""
    pass

class DattoApiError(Error):
    """Raised on errors encountered from the Datto API."""
    pass


class Datto:
    """
    Handles the session and communication with the Datto API.
    """
    def __init__(self):
        '''Constructor - initialize Python Requests Session and get XML API data'''
        # create intial session and set parameters
        logger.info('Creating new python requests session with the API endpoint.')
        self.session = requests.Session()
        self.session.auth = (AUTH_USER, AUTH_PASS)
        self.session.headers.update({"Content-Type" : "application/json"})

        self.test_api_connection()
        self.xml_api_root = self.get_xml_api_data()

    @retry(DattoApiError, tries=3, delay=3, logger=logger)
    def test_api_connection(self):
        """Make a connection to the API Base URL to test connectivity and credentials.
        Store the initial device query for later use.
        """
        logger.info("Retrieving initial asset list.")
        self.assets = self.session.get(API_BASE_URI + '?_page=1').json()
        if 'code' in self.assets:
            raise DattoApiError("Error querying API for devices")
        return

    def get_xml_api_data(self):
        '''Retrieve and parse data from XML API
        Returns xml ElementTree of Datto XML content'''
        logger.info('Retrieving Datto XML API data.')
        xml_request = requests.Session()
        xml_request.headers.update({"Content-Type" : "application/xml"})
        api_xml_data = xml_request.get(XML_API_URI).text
        xml_request.close()
        return(ET.fromstring(api_xml_data))

    @retry(DattoApiError, tries=3, delay=3, logger=logger)
    def getDevices(self):
        '''
        Use the initial device API query to load all devices
         -Check pagination details and iterate through any additional pages
          to return a list of all devices
        Returns a list of all 'items' from the devices API.
        '''

        devices = []
        devices.extend(self.assets['items']) # load the first (up to) 100 devices into device list
        totalPages = self.assets['pagination']['totalPages'] # see how many pages there are

        # new request for each page; extend additional 'items' to devices list
        if totalPages > 1:
            for page in range(2, totalPages+1):
                logger.info("Querying API for additional devices.")
                r = self.session.get(API_BASE_URI + '?_page=' + str(page)).json()
                if 'code' in r:
                    raise DattoApiError("Error querying Datto API for second page of devices")
                devices.extend(r['items'])

        devices = sorted(devices, key= lambda i: i['name'].upper()) # let's sort this bad boy!
        return devices

    @retry(DattoApiError, tries=3, delay=3, logger=logger)
    def getAssetDetails(self,serialNumber):
        """
        With a device serial number (argument), query the API with it
        to retrieve JSON data with the asset info for that device.

        Returns JSON data (dictionary) for the device with the given serial number
        """

        logger.debug("Querying API for device asset details.")
        asset_data = self.session.get(API_BASE_URI + '/' + serialNumber + '/asset').json()

        if 'code' in asset_data:
            raise DattoApiError('Error encountered retrieving asset details for "{}"'.format(asset_data['name']))

        return asset_data

    def rebuildScreenshotUrl(self,url):
        '''Rebuild the URL using the latest API calls'''

        baseUrl = 'https://device.dattobackup.com/sirisReporting/images/latest'

        o = urlparse(url)
        imageName = o.query.split('/')[-1]
        newUrl = '/'.join([baseUrl, imageName])

        return newUrl

    def getAgentScreenshot(self,deviceName,agentName):

        logger.debug(f"Retrieving screenshot URL for '{agentName}' on '{deviceName}'")
        # Find 'Device' elements.  If it matches, find the target agent and get screenshot URI.
        for xml_device in self.xml_api_root.findall('Device'):

            # Iterate through devices to find the target device
            xml_hostname = xml_device.find('Hostname')
            if xml_hostname.text == deviceName:

                # Iterate through device agents to find target agent
                backup_volumes = xml_device.find('BackupVolumes')
                for backup_volume in backup_volumes.findall('BackupVolume'):
                    xml_agent_name = backup_volume.find('Volume')

                    # If agent name matches, get screenshot URI and return
                    if xml_agent_name.text == agentName:
                        screenshotURI = ""
                        screenshotURI = backup_volume.find('ScreenshotImagePath').text

                        #check to see if the old API is being used; correct if so
                        if 'partners.dattobackup.com' in screenshotURI:
                            screenshotURI = self.rebuildScreenshotUrl(screenshotURI)

                        if backup_volume.find('ScreenshotError').text:
                            screenshotErrorMessage = backup_volume.find('ScreenshotError').text
                        else:
                            screenshotErrorMessage = "[error message not available]"
                        return(screenshotURI, screenshotErrorMessage)
        return(-1,-1)

    def sessionClose(self):
        """Close the "requests" session"""

        logger.info('Closing requests session')
        return self.session.close()

def appendError(error_detail, color=None):
    '''Append an error to the results_data list.

        error_detail - List of error data.
            First and second items are error level, and device name
    '''
    if color: error_detail.append(color)
    results_data[error_detail[0]].append(error_detail)
    return

def buildEmailBody(results_data):
    """Compile all results into HTML tables based on error level."""

    logger.info('Building HTML email message body.')
    # create initial html structure
    MSG_BODY = '<html><head><style>table,th,td{border:1px solid black;border-collapse: collapse; text-align: left;}th{text-align:center;}</style></head><body>'

    if results_data['critical']:
        MSG_BODY += '<h1>CRITICAL ERRORS</h1><table>'
        MSG_BODY += '<tr><th>Appliance</th><th>Error Type</th><th>Error Details</th></tr>'
        for error in results_data['critical']:
            MSG_BODY += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td></tr>'
        MSG_BODY += '</table>'

    if results_data['backup_error']:
        MSG_BODY += '<h1>Backup Errors</h1><table>\
        <tr><th>Appliance</th><th>Agent/Share</th><th>Last Backup</th><th>Error Details</th></tr>'
        for error in results_data['backup_error']:
            if len(error) == 5:
                MSG_BODY += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td><td>' + error[4] + '</td></tr>'
            else:
                MSG_BODY += '<tr style="background-color: {0};"><td>'.format(error[5]) + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td><td>' + error[4] + '</td></tr>'
        MSG_BODY += '</table>'

    if results_data['offsite_error']:
        MSG_BODY += '<h1>Off-Site Sync Issues</h1><table>\
        <tr><th>Appliance</th><th>Agent/Share</th><th>Error Details</th></tr>'
        for error in results_data['offsite_error']:
            if len(error) == 4:
                MSG_BODY += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td></tr>'
            else:
                MSG_BODY += '<tr style="background-color: {0};"><td>'.format(error[4]) + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td></tr>'
        MSG_BODY += '</table>'

    if results_data['screenshot_error']:
        MSG_BODY += '<h1>Screenshot Failures</h1><table>\
        <tr><th>Appliance</th><th>Agent</th><th>Screenshot</th></tr>'
        for error in results_data['screenshot_error']:
            if not error[3]:
                col_three = 'No Data'
            elif error[3].startswith('http'):
                col_three = '<a href="{0}"><img src="{0}" alt="" width="160" title="{1}"></img></a>'.format(error[3], error[4])
            else:
                col_three = error[3]
            if len(error) == 5:
                MSG_BODY += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td width="160">' + col_three + '</td></tr>'
            else:
                MSG_BODY += '<tr style="background-color: {0};"><td>'.format(error[5]) + error[1] + '</td><td>' + error[2] + '</td><td width="160">' + col_three + '</td></tr>'
        MSG_BODY += '</table>'

    if results_data['verification_error']:
        MSG_BODY += '<h1>Local Verification Issues</h1><table>\
        <tr><th>Appliance</th><th>Agent</th><th>Error Type</th><th>Error Message</th></tr>'
        for error in results_data['verification_error']:
            if error[4]:
                error_message = error[4]
            else:
                error_message = '<none>'
            MSG_BODY += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td><td>' + error_message + '</td></tr>'
        MSG_BODY += '</table>'

    if results_data['informational']:
        MSG_BODY += '<h1>Informational</h1><table>\
        <tr><th>Appliance</th><th>Agent/Share</th><th>Details</th></tr>'
        for error in results_data['informational']:
            MSG_BODY += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td></tr>'
        MSG_BODY += '</table>'

    MSG_BODY += '</body></html>'
    return(MSG_BODY)

def display_time(seconds, granularity=2):
    # from "Mr. B":
    # https://stackoverflow.com/questions/4048651/python-function-to-convert-seconds-into-minutes-hours-and-days/24542445#answer-24542445
    intervals = (
        ('weeks', 604800),  # 60 * 60 * 24 * 7
        ('days', 86400),    # 60 * 60 * 24
        ('hours', 3600),    # 60 * 60
        ('minutes', 60),
        ('seconds', 1),
        )

    seconds = int(seconds)
    result = []

    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append("{} {}".format(value, name))
    return ', '.join(result[:granularity])

def email_report():
    """Email error report to listed recipients.

    If using Office 365 and only sending to recipients in the
    same domain, it's best to use the "direct send" method because
    authentication is not required. See Option 2 here (you'll need a send connector for this):

    https://docs.microsoft.com/en-us/exchange/mail-flow-best-practices/how-to-set-up-a-multifunction-device-or-application-to-send-email-using-office-3
    """
    logger.info("Sending email report to: {}".format(args.email_to))
    d = datetime.datetime.today()

    # Email heads
    msg = MIMEMultipart()
    msg['Subject'] = 'Daily Datto Check: {}'.format(d.strftime('%m/%d/%Y'))
    msg['From'] = args.email_from
    msg['To'] = ', '.join(args.email_to)
    if args.email_cc:
        msg['Cc'] = ', '.join(args.email_cc)
    msg.attach(MIMEText(MSG_BODY, 'html'))

    # Send email
    s = smtplib.SMTP(host=args.mx_endpoint, port=args.smtp_port)

    try:
        if args.starttls:
            s.starttls()
        if args.email_pw:
            s.login(args.email_from, args.email_pw)
        s.send_message(msg)
        s.quit()
    except Exception as e:
        logger.critical(f"Failed to send email message!\n  {str(e)}")
        pass
    return


# initialize results_data, used for generating html report
results_data = {'critical' : [],
                'backup_error' : [],
                'offsite_error' : [],
                'screenshot_error' : [],
                'verification_error' : [],
                'informational' : []
                }

if not args.verbose:
    print("\nRUNNING SCRIPT (to enable console output, use '-v' or '--verbose')")
    print("\n  -- Running Datto Check Script --")

logger.info("Starting Datto Check Script")
dattoAPI = Datto()
devices = dattoAPI.getDevices()

# main loop
logger.info('Entering main script loop')
try:
    for device in devices:

        if device['hidden']:
            logger.debug(f"Skipping hidden asset: {device['name']}.")
            continue
        if device['name'] == 'backupDevice': continue

        #######################
        ###  DEVICE CHECKS  ###
        #######################

        logger.debug(f" --- Starting device and agent checks for '{device['name']}' ---")

        # Check to see if there are any active tickets
        if device['activeTickets']:
            error_text = 'Appliance has {} active {}'.format(\
                device['activeTickets'], 'ticket' if device['activeTickets'] < 2 else 'tickets' )
            appendError(['informational', device['name'], 'N/A', error_text])
            logger.debug(f"{device['name']}: {error_text}")

        # Last checkin time
        t = device['lastSeenDate'][:22] + device['lastSeenDate'][23:] # remove the colon from time zone
        device_checkin = datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%S%z")
        now = datetime.datetime.now(datetime.timezone.utc) # make 'now' timezone aware
        timeDiff = now - device_checkin

        if timeDiff.total_seconds() >= CHECKIN_LIMIT:
            error_text = "Last checkin was {} ago.".format(display_time(timeDiff.total_seconds()))
            appendError(['critical', device['name'], 'Appliance Offline', error_text])
            logger.debug(f"{device['name']}: Appliance Offline")
            continue  # do not proceed if the device is offline; go to next device

        # Check Local Disk Usage
        storage_available = int(device['localStorageAvailable']['size'])
        storage_used = int(device['localStorageUsed']['size'])
        total_space = storage_available + storage_used
        try:
            available_pct = float("{0:.2f}".format(storage_used / total_space)) * 100
        except ZeroDivisionError as e:
            logger.error('"{}" calculating free space (API returned null value) on device: "{}"'.format(str(e),device['name']))
            continue

        if available_pct > STORAGE_PCT_THRESHOLD:
            error_text = 'Local storage exceeds {}%.  Current Usage: {}%'.\
                          format(str(STORAGE_PCT_THRESHOLD), str(available_pct))
            appendError(['critical', device['name'], 'Low Disk Space',error_text])
            logger.debug(f"{device['name']}: {error_text}")

        ######################
        #### AGENT CHECKS ####
        ######################

        # query the API with the device S/N to get asset info
        assetDetails = dattoAPI.getAssetDetails(device['serialNumber'])

        for agent in assetDetails:
            try:
                if agent['isArchived']:
                    logger.debug(f"Agent {agent['name']} is archived.")
                    continue
                if agent['isPaused']:
                    logger.debug(f"Agent {agent['name']} is paused.")
                    continue
            except Exception as e:
                logger.critical('"{}" (device: "{}")'.format(str(e), device['name']))
                continue

            BACKUP_FAILURE = False

            # check if the most recent backup was more than LAST_BACKUP_THRESHOLD
            lastBackupTime = datetime.datetime.fromtimestamp(agent['lastSnapshot'], datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            timeDiff = now - lastBackupTime

            if timeDiff.total_seconds() > LAST_BACKUP_THRESHOLD:
                try:
                    if agent['backups'][0]['backup']['status'] != 'success':  # only error if the last scheduled backup failed
                        backup_error = agent['backups'][0]['backup']['errorMessage']
                        if not backup_error:
                            backup_error = "No error message available"
                        # check if local backup points exist
                        if agent['lastSnapshot']:
                            lastSnapshotTime = str(display_time(timeDiff.total_seconds())) + ' ago'
                        else:
                            lastSnapshotTime = "(no local snapshots exist)"
                        error_text = '-- "{}": Last scheduled backup failed; last backup was: {}. Error: "{}"'.format(\
                            agent['name'], lastSnapshotTime, backup_error)

                        BACKUP_FAILURE = True
                        errorData = ['backup_error', device['name'], agent['name'],'{}'.format(lastSnapshotTime), backup_error]

                        if timeDiff.total_seconds() > ACTIONABLE_THRESHOLD and agent['lastSnapshot']:
                            appendError(errorData, color='red')
                        else:
                            appendError(errorData)
                        logger.debug(error_text)

                except IndexError:
                    error_text = 'Agent does not seem to have any backups'
                    logger.debug(f"Agent {agent['name']} does not seem to have any backups.")
                    appendError(['informational', device['name'], agent['name'], error_text])

            # Check time since latest off-site point; alert if more than LAST_OFFSITE_THRESHOLD
            if not agent['latestOffsite']:
                error_text = 'No off-site backup points exist'
                appendError(['informational', device['name'], agent['name'], error_text])
                logger.debug(f"{agent['name']} - {error_text}")
            elif not BACKUP_FAILURE:
                lastOffsite = datetime.datetime.fromtimestamp(agent['latestOffsite'], datetime.timezone.utc)
                timeDiff = now - lastOffsite
                if timeDiff.total_seconds() > LAST_OFFSITE_THRESHOLD:
                    error_text = 'Last off-site: {} ago'.format(display_time(timeDiff.total_seconds()))
                    if timeDiff.total_seconds() > ACTIONABLE_THRESHOLD:
                        appendError(['offsite_error', device['name'], agent['name'], error_text], 'red')
                    else:
                        appendError(['offsite_error', device['name'], agent['name'], error_text])
                    logger.debug(f"{agent['name']} - {error_text}")

            # check time of last screenshot
            if agent['type'] == 'agent' and agent['lastScreenshotAttempt'] and not BACKUP_FAILURE:
                last_screenshot = datetime.datetime.fromtimestamp(agent['lastScreenshotAttempt'], datetime.timezone.utc)
                timeDiff = now - last_screenshot
                if timeDiff.total_seconds() > LAST_SCREENSHOT_THRESHOLD:
                    error_text = 'Last screenshot was {} ago.'.format(display_time(timeDiff.total_seconds()))
                    if timeDiff.total_seconds() > ACTIONABLE_THRESHOLD:
                        appendError(['screenshot_error', device['name'], agent['name'], error_text, '', 'red'])
                    else:
                        appendError(['screenshot_error', device['name'], agent['name'], error_text, ''])
                    logger.debug(f"{agent['name']} - {error_text}")

            # check status of last screenshot attempt
            if not BACKUP_FAILURE and agent['type'] == 'agent' and agent['lastScreenshotAttemptStatus'] == False:
                error_text = 'Last screenshot attempt failed!'
                screenshotURI,screenshotErrorMessage = dattoAPI.getAgentScreenshot(device['name'], agent['name'])
                if screenshotURI == -1:
                    screenshotURI = ""
                    screenshotErrorMessage = ""
                appendError(['screenshot_error', device['name'], agent['name'], screenshotURI, screenshotErrorMessage])
                logger.debug(f"{agent['name']} - {error_text}")

            # check local verification and report any errors
            try:
                if not BACKUP_FAILURE and agent['type'] == 'agent' and agent['backups'] and agent['backups'][0]['localVerification']['errors']:
                    for error in agent['backups'][0]['localVerification']['errors']:
                        error_text = 'Local Verification Failure!\n{}\n{}'.format(error['errorType'],error['errorMessage'])
                        appendError(['verification_error', device['name'], agent['name'], error['errorType'], error['errorMessage']])
                        logger.debug(f"{agent['name']} - {error_text}")
            except Exception as e:
                logger.error('Device: "{}" Agent: "{}". {}'.format(device['name'], agent['name'], str(e)))

    dattoAPI.sessionClose()

except Exception as e:
    logger.fatal('Device: {} - "{}"\n{}'.format(device['name'], str(e), traceback.format_exc()))
    logger.info("Datto check script finished with errors.")
    sys.exit(dattoAPI.sessionClose())

if SEND_EMAIL:
    import smtplib
    from email.mime.application import MIMEApplication
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    try:
        MSG_BODY = buildEmailBody(results_data).strip('\n')
    except Exception as e:
        logger.error('Failed to build email body')
        MSG_BODY = '<pre>\nFailed to build HTML email report.  This was likely caused by the API returning corrupt (or empty) data for a device.\n\n'
        MSG_BODY += 'Error & Traceback:\n\n"{}"\n{}</pre>'.format(str(e), traceback.format_exc())

    email_report()

logger.info("Datto check script complete.")
sys.exit(0)
