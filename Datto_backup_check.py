#!/usr/bin/python3
'''
//TODO: 
    1. Consolidate errors per agent if there are multiple
    2. Create new email format for errors; use table to list errors in order of severity
    3. Add screenshot download using XML API; add to email.
    4. Implement argparse
'''

import requests, sys, datetime

# check to make sure we have API credentials; exit if not provided
if len(sys.argv) < 3:
    print('\n[!] Please provide the API username & password!')
    print('    Usage:  python3 {} <API username> <API password>\n'.format(sys.argv[0]))
    sys.exit(1)
    
# Global Variables
API_BASE_URI = 'https://api.datto.com/v1/bcdr/device'
AUTH_USER = sys.argv[1]
AUTH_PASS = sys.argv[2]

## Set this to True to send the report email:
SEND_EMAIL = False

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
        '''Constructor - initialize Python Requests Session'''
        # create intial session and set parameters
        self.session = requests.Session()
        self.session.auth = (AUTH_USER, AUTH_PASS)
        self.session.headers.update({"Conent-Type" : "applicaion/json"})
        
        r = self.session.get(API_BASE_URI).json()  # test the connection
        if 'code' in r: 
            print('[!]   Critical Error:  "{}"'.format(r['message']))
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
    
    Arguments: 
        device_name - Name of the Datto Appliance
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
            MSG_BODY += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</tr>'
        MSG_BODY += '</table>'
            
    if results_data['alert']:
        MSG_BODY += '<h1>ALERTS</h1><table>\
        <tr><th>Appliance</th><th>Agent/Share</th><th>Error Type</th><th>Error Details</th></tr>'
        for error in results_data['alert']:
            MSG_BODY += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td><td>' + error[4] + '</tr>'
        MSG_BODY += '</table>'
        
    if results_data['error']:
        MSG_BODY += '<h1>ERRORS</h1><table>\
        <tr><th>Appliance</th><th>Agent/Share</th><th>Error Details</th></tr>'
        for error in results_data['error']:
            MSG_BODY += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</tr>'
        MSG_BODY += '</table>'
        
    if results_data['info']:
        MSG_BODY += '<h1>INFO</h1><table>\
        <tr><th>Appliance</th><th>Agent/Share</th><th>Error Details</th></tr>'
        for error in results_data['info']:
            MSG_BODY += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</tr>'
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
    authentication is not required. See Option 2 here:
    
    https://docs.microsoft.com/en-us/exchange/mail-flow-best-practices/how-to-set-up-a-multifunction-device-or-application-to-send-email-using-office-3
    """

    # Email heads
    msg = MIMEMultipart()
    msg['Subject'] = 'Daily Datto Check: {}'.format(d.strftime('%m/%d/%Y'))
    msg['From'] = 'datto-check@domain.com'
    msg['To'] = 'username@example.com'
    #msg['Cc'] = ', '.join(config.EMAIL_CC)
    msg.attach(MIMEText('\n'.join(MSG_BODY)))

    # Send email
    s = smtplib.SMTP(host='<Insert MX Endpoint>', port=25)
    s.starttls()
    #s.login(EMAIL_FROM, EMAIL_PASSWD)
    s.send_message(msg)
    s.quit()
    return
        
dattoAPI = Datto()
devices = dattoAPI.getDevices()

# initialize results_data, used for generating html report
results_data = {'critical' : [],
                'alert' : [],
                'error' : [],
                'info' : []
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
            appendError(['info', device['name'], 'N/A', error_text])        
            errors.append(error_text)

        # Last checkin time
        t = device['lastSeenDate'][:22] + device['lastSeenDate'][23:] # remove the colon from time zone
        device_checkin = datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%S%z")
        now = datetime.datetime.now(datetime.timezone.utc) # make 'now' timezone aware
        timeDiff = now - device_checkin
    
        if timeDiff.total_seconds() >= CHECKIN_LIMIT:
            error_text = "Last checkin was {} ago!".format(display_time(timeDiff.total_seconds()))
            errors.append(error_text)
            appendError(['critical', device['name'], 'Device Offline',error_text])
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
                        error_text = 'Last scheduled backup failed; last backup was {} ago. Error: "{}"'.format(\
                            display_time(timeDiff.total_seconds()), 
                            agent['backups'][0]['backup']['errorMessage'])
                        BACKUP_FAILURE = True
                        errors.append(error_text)
                        appendError(['alert', device['name'], agent['name'], 'Backup Failure', error_text])
                except IndexError:
                    error_text = 'Agent does not seem to have any backups'
                    errors.append(error_text)
                    appendError(['info', device['name'], agent['name'], error_text])
                    
            # Check time since latest off-site point; alert if more than LAST_OFFSITE_THRESHOLD
            if not agent['latestOffsite']:
                error_text = 'No off-site backup points exist'
                errors.append(error_text)
                appendError(['info', device['name'], agent['name'], error_text])
            elif not BACKUP_FAILURE:
                lastOffsite = datetime.datetime.fromtimestamp(agent['latestOffsite'], datetime.timezone.utc)
                timeDiff = now - lastOffsite
                if timeDiff.total_seconds() > LAST_OFFSITE_THRESHOLD:
                    error_text = 'Last off-site was {} ago'.format(display_time(timeDiff.total_seconds()))
                    errors.append(error_text)
                    appendError(['error', device['name'], agent['name'], error_text])
                    
            # check time of last screenshot
            if agent['type'] == 'agent' and agent['lastScreenshotAttempt'] and not BACKUP_FAILURE:
                last_screenshot = datetime.datetime.fromtimestamp(agent['lastScreenshotAttempt'], datetime.timezone.utc)
                timeDiff = now - last_screenshot
                if timeDiff.total_seconds() > LAST_SCREENSHOT_THRESHOLD:
                    error_text = 'Last screenshot attempt was {} ago.'.format(display_time(timeDiff.total_seconds()))
                    errors.append(error_text)
                    appendError(['alert', device['name'], agent['name'], 'No recent screenshot', error_text])
                    
            # check status of last screenshot attempt
            if not BACKUP_FAILURE and agent['type'] == 'agent' and agent['lastScreenshotAttemptStatus'] == False:
                error_text = 'Last screenshot attempt failed!'
                errors.append(error_text)
                appendError(['alert', device['name'], agent['name'], 'Screenshot Failure', error_text])

            # check local verification and report any errors
            try:
                if not BACKUP_FAILURE and agent['type'] == 'agent' and agent['backups'] and agent['backups'][0]['localVerification']['errors']:
                    for error in agent['backups'][0]['localVerification']['errors']:
                        error_text = 'Local Verification Failure!\n{}\n{}'.format(error['errorType'],error['errorMessage'])
                        errors.append(error_text)
                        appendError(['error', device['name'], agent['name'], error_text])
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
