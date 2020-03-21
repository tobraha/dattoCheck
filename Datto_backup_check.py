#!/usr/bin/python3
'''
//TODO: 
    1. Add screenshot download using XML API; add to email.
'''

import requests
import sys
import datetime
import argparse
from xml.etree import ElementTree

__authors__ = ["Tommy Harris"]
__date__ = '08SEP2019'
__description__ = '''Using the Datto API, get information on current status of backups, screenshots, local verification,\
and device issues.

To send the results as an email, provide the optional email parameters.'''

parser = argparse.ArgumentParser(description=__description__,
                                 epilog='Developed by {} on {}'.format(", ".join(__authors__), __date__ ))

# Add positional arguments
parser.add_argument('AUTH_USER', help='Datto API User (REST API Public Key)')
parser.add_argument('AUTH_PASS', help='Datto API Password (REST API Secret Key')
parser.add_argument('XML_API_KEY', help='Datto XML API Key')

# Optional arguments
parser.add_argument('--send-email', help='Set this flag to send an email.  Below parameters required if set', action='store_true')
parser.add_argument('--email-to', help='Email address to send message to. Use more than once for multiple recipients.',
                    action='append',
                    required=True)
parser.add_argument('--email-cc',help='(OPTIONAL) Email address to CC. Use more than once for multiple recipients.',
                    action='append')
parser.add_argument('--email-from', help='Email address to send message from', required=True)
parser.add_argument('--email-pw', help='Password to use for authentication')
parser.add_argument('--mx-endpoint', help='MX Endpoint of where to send the email', required=True)
parser.add_argument('--smtp-port', help='TCP port to use when sending the email', type=int, choices=['25', '587'], default='25')
parser.add_argument('--starttls', help='Specify whether to use STARTTLS or not', action='store_true')

# Parsing and using the arguments
args = parser.parse_args()
    
# Global Variables
API_BASE_URI = 'https://api.datto.com/v1/bcdr/device'
XML_API_URI = 'https://portal.dattobackup.com/external/api/xml/status/{0}'.format(args.XML_API_KEY)
AUTH_USER = args.AUTH_USER
AUTH_PASS = args.AUTH_PASS

## Set this to True to send the report email:
SEND_EMAIL = False
if args.send_email:
    SEND_EMAIL = True

# Error/Alert threshold settings
CHECKIN_LIMIT = 60 * 20                  # threshold for device offline time 
STORAGE_PCT_THRESHOLD = 95               # threshold for local storage; in percent
LAST_BACKUP_THRESHOLD = 60 * 60 * 12     # threshold for failed backup time
LAST_OFFSITE_THRESHOLD = 60 * 60 * 72    # threshold for last successful off-site
LAST_SCREENSHOT_THRESHOLD = 60 * 60 * 48 # threshold for last screenshot taken

class Datto:
    """
    Handles the session and communication with the Datto API.
    """
    def __init__(self):
        '''Constructor - initialize Python Requests Session and get XML API data'''
        # create intial session and set parameters
        self.session = requests.Session()
        self.session.auth = (AUTH_USER, AUTH_PASS)
        self.session.headers.update({"Conent-Type" : "applicaion/json"})
        
        r = self.session.get(API_BASE_URI).json()  # test the connection
        if 'code' in r: 
            print('[!]   Critical Failure:  "{}"'.format(r['message']))
            sys.exit(1)
    
    def getDevices(self):
        '''        
        Query the Datto API for all 'Devices'
         -Check pagination details and iterate through any additional pages
          to return a list of all devices
        Returns a list of all 'items' from the devices API.
        '''        
        r = self.session.get(API_BASE_URI + '?_page=1').json() # initial request
        
        devices = [] 
        devices.extend(r['items']) # load the first (up to) 100 devices into device list
        totalPages = r['pagination']['totalPages'] # see how many pages there are
        
        # new request for each page; extend additional 'items' to devices list
        if totalPages > 1:
            for page in range(2, totalPages+1):
                r = self.session.get(API_BASE_URI + '?_page=' + str(page)).json()
                devices.extend(r['items'])
                
        devices = sorted(devices, key= lambda i: i['name'].upper()) # let's sort this bad boy!
        return devices

    def getAssetDetails(self,serialNumber):
        '''
        With a device serial number (argument), query the API with it
        to retrieve JSON data with the asset info for that device.
        
        Returns JSON data (dictionary) for the device with the given serial number
        '''
        return self.session.get(API_BASE_URI + '/' + serialNumber + '/asset').json()
        
    def sessionClose(self):
        '''Close the "requests" session'''
        return self.session.close()

def appendError(error_detail):
    '''Append an error to the results_data list.
    
        error_detail - List of error data. 
            First and second items are error level, and device name
    '''
    results_data[error_detail[0]].append(error_detail)
    return

def buildEmailBody(results_data):
    '''Compile all results into HTML tables based on error level.
    '''
    # create initial html structure
    MSG_BODY = '<html><head><style>table,th,td{border:1px solid black;border-collapse: collapse; text-align: left;}</style></head><body>'
    
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
            MSG_BODY += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td><td>' + error[4] + '</td></tr>'
        MSG_BODY += '</table>'
        
    if results_data['offsite_error']:
        MSG_BODY += '<h1>Off-Site Sync Issues</h1><table>\
        <tr><th>Appliance</th><th>Agent/Share</th><th>Error Details</th></tr>'
        for error in results_data['offsite_error']:
            MSG_BODY += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td></tr>'
        MSG_BODY += '</table>'

    if results_data['screenshot_error']:
        MSG_BODY += '<h1>Screenshot Failures</h1><table>\
        <tr><th>Appliance</th><th>Agent</th><th>Screenshot</th></tr>'
        for error in results_data['screenshot_error']:
            MSG_BODY += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td></tr>'
        MSG_BODY += '</table>'
        
    if results_data['informational']:
        MSG_BODY += '<h1>Informational</h1><table>\
        <tr><th>Appliance</th><th>Agent/Share</th><th>Details</th></tr>'
        for error in results_data['informational']:
            MSG_BODY += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td></tr>'
        MSG_BODY += '</table>'
        
    MSG_BODY += '</body></html>'    
    return(MSG_BODY)

def printErrors(errors, device_name):
    header = '\n--DEVICE: {}'.format(device_name)
    print(header)
    #MSG_BODY.append(header)
    for error in errors:
        print(error)
        #MSG_BODY.append(error)
    
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
    if args.starttls:
        s.starttls()
    if args.EMAIL_PW:
        s.login(args.email_from, args.email_pw)
    s.send_message(msg)
    s.quit()
    return
        
dattoAPI = Datto()
devices = dattoAPI.getDevices()

# initialize results_data, used for generating html report
results_data = {'critical' : [],
                'backup_error' : [],
                'offsite_error' : [],
                'screenshot_error' : [],
                'verification_error' : [],
                'informational' : []
                }

# main loop
try:      # catch KeyboardInterrupt
    for device in devices:
        
        if device['hidden']: continue # skip hidden devices in the portal
        if device['name'] == 'backupDevice': continue # skip unnamed devices
        
        errors = []
        
        #######################
        ###  DEVICE CHECKS  ###
        #######################

        # Check to see if there are any active tickets
        if device['activeTickets']:
            error_text = 'Appliance has {} active {}'.format(\
                device['activeTickets'], 'ticket' if device['activeTickets'] < 2 else 'tickets' )
            appendError(['informational', device['name'], 'N/A', error_text])
            errors.append(error_text)

        # Last checkin time
        t = device['lastSeenDate'][:22] + device['lastSeenDate'][23:] # remove the colon from time zone
        device_checkin = datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%S%z")
        now = datetime.datetime.now(datetime.timezone.utc) # make 'now' timezone aware
        timeDiff = now - device_checkin
    
        if timeDiff.total_seconds() >= CHECKIN_LIMIT:
            error_text = "Last checkin was {} ago.".format(display_time(timeDiff.total_seconds()))
            errors.append(error_text)
            appendError(['critical', device['name'], 'Appliance Offline',error_text])
            printErrors(errors, device['name'])
            continue  # do not proceed if the device is offline; go to next device
        
        # Check Local Disk Usage
        storage_available = int(device['localStorageAvailable']['size'])
        storage_used = int(device['localStorageUsed']['size'])    
        total_space = storage_available + storage_used
        available_pct = float("{0:.2f}".format(storage_used / total_space)) * 100
        
        if available_pct > STORAGE_PCT_THRESHOLD:
            error_text = 'Local storage exceeds {}%.  Current Usage: {}%'.\
                          format(str(STORAGE_PCT_THRESHOLD), str(available_pct))
            appendError(['critical', device['name'], 'Low Disk Space',error_text])
            errors.append(error_text)                        
            
        ######################
        #### AGENT CHECKS ####
        ######################
        
        # query the API with the device S/N to get asset info
        assetDetails = dattoAPI.getAssetDetails(device['serialNumber'])
        
        for agent in assetDetails:
            if agent['isArchived']: continue
            if agent['isPaused']: continue
            
            BACKUP_FAILURE = False

            # check if the most recent backup was more than LAST_BACKUP_THRESHOLD
            lastBackupTime = datetime.datetime.fromtimestamp(agent['lastSnapshot'], datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            timeDiff = now - lastBackupTime
            
            if timeDiff.total_seconds() > LAST_BACKUP_THRESHOLD:
                try:
                    if agent['backups'][0]['backup']['status'] != 'success':  # only error if the last scheduled backup failed
                        backup_error = agent['backups'][0]['backup']['errorMessage']
                        error_text = 'Last scheduled backup failed; last backup was {} ago. Error: "{}"'.format(\
                            display_time(timeDiff.total_seconds()), 
                            backup_error)
                        BACKUP_FAILURE = True
                        errors.append(error_text)
                        appendError(['backup_error',
                                     device['name'],
                                     agent['name'],
                                     '{} ago.'.format(display_time(timeDiff.total_seconds())),
                                     backup_error])
                except IndexError:
                    error_text = 'Agent does not seem to have any backups'
                    errors.append(error_text)
                    appendError(['informational', device['name'], agent['name'], error_text])
                    
            # Check time since latest off-site point; alert if more than LAST_OFFSITE_THRESHOLD
            if not agent['latestOffsite']:
                error_text = 'No off-site backup points exist'
                errors.append(error_text)
                appendError(['informational', device['name'], agent['name'], error_text])
            elif not BACKUP_FAILURE:
                lastOffsite = datetime.datetime.fromtimestamp(agent['latestOffsite'], datetime.timezone.utc)
                timeDiff = now - lastOffsite
                if timeDiff.total_seconds() > LAST_OFFSITE_THRESHOLD:
                    error_text = 'Last off-site: {} ago'.format(display_time(timeDiff.total_seconds()))
                    errors.append(error_text)
                    appendError(['offsite_error', device['name'], agent['name'], error_text])
                    
            # check time of last screenshot
            if agent['type'] == 'agent' and agent['lastScreenshotAttempt'] and not BACKUP_FAILURE:
                last_screenshot = datetime.datetime.fromtimestamp(agent['lastScreenshotAttempt'], datetime.timezone.utc)
                timeDiff = now - last_screenshot
                if timeDiff.total_seconds() > LAST_SCREENSHOT_THRESHOLD:
                    error_text = 'Last screenshot was {} ago.'.format(display_time(timeDiff.total_seconds()))
                    errors.append(error_text)
                    appendError(['screenshot_error', device['name'], agent['name'], error_text, ''])
                    
            # check status of last screenshot attempt
            if not BACKUP_FAILURE and agent['type'] == 'agent' and agent['lastScreenshotAttemptStatus'] == False:
                error_text = 'Last screenshot attempt failed!'
                errors.append(error_text)
                appendError(['screenshot_error', device['name'], agent['name'], '###--COMING SOON--###'])

            # check local verification and report any errors
            try:
                if not BACKUP_FAILURE and agent['type'] == 'agent' and agent['backups'] and agent['backups'][0]['localVerification']['errors']:
                    for error in agent['backups'][0]['localVerification']['errors']:
                        error_text = 'Local Verification Failure!\n{}\n{}'.format(error['errorType'],error['errorMessage'])
                        errors.append(error_text)
                        appendError(['verification_error', device['name'], agent['name'], error['errorType'], error['errorMessage']])
            except Exception as e:
                print('\nException Caught: {}'.format(e))
                print('-- [!] -- Error checking local verification for agent "{}".  Moving on!'.format(agent['name']))

        if errors: printErrors(errors, device['name'])

    dattoAPI.sessionClose()
    MSG_BODY = buildEmailBody(results_data).strip('\n')
    if SEND_EMAIL:
        import smtplib
        from email.mime.application import MIMEApplication
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        email_report()

    sys.exit(0)
except KeyboardInterrupt:
    sys.exit(dattoAPI.sessionClose())
