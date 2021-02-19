import logging
import datetime
import traceback
import config
import sys

# Import: Others
import requests
from retry import retry
from urllib.parse import urlparse
from logging.handlers import RotatingFileHandler
from xml.etree import ElementTree as ET

class Datto():
    """
    Handles the session and communication with the Datto API.
    """
    def __init__(self, user, password, xmlKey):
        '''Constructor - initialize Python Requests Session and get XML API data'''

        self.logger = logging.getLogger()
        self.logger.info('Creating new Python requests session with the API endpoint.')
        self.session = requests.Session()
        self.session.auth = (user, password)
        self.session.headers.update({"Content-Type" : "application/json"})

        self.test_api_connection()
        self.xml_api_root = self.get_xml_api_data(xmlKey)

    @retry(config.DattoApiError, tries=3, delay=3, logger=logging.getLogger())
    def test_api_connection(self):
        """Make a connection to the API Base URL to test connectivity and credentials.
        Store the initial device query for later use.
        """

        self.logger.info("Retrieving initial asset list.")
        self.assets = self.session.get(config.API_BASE_URI + '?_page=1').json()
        if 'code' in self.assets:
            raise config.DattoApiError("Error querying API for devices")
        return

    def get_xml_api_data(self, xmlKey):
        """Retrieve and parse data from XML API
        Returns xml ElementTree of Datto XML content"""

        self.logger.info('Retrieving Datto XML API data.')
        xml_request = requests.Session()
        xml_request.headers.update({"Content-Type" : "application/xml"})
        url = config.XML_API_BASE_URI + '/' + xmlKey
        api_xml_data = xml_request.get(url).text
        xml_request.close()
        return(ET.fromstring(api_xml_data))

    @retry(config.DattoApiError, tries=3, delay=3, logger=logging.getLogger())
    def getDevices(self):
        """
        Use the initial device API query to load all devices
         -Check pagination details and iterate through any additional pages
          to return a list of all devices
        Returns a list of all 'items' from the devices API.
        """

        devices = []
        devices.extend(self.assets['items']) # load the first (up to) 100 devices into device list
        totalPages = self.assets['pagination']['totalPages'] # see how many pages there are

        # new request for each page; extend additional 'items' to devices list
        if totalPages > 1:
            for page in range(2, totalPages+1):
                self.logger.info("Querying API for additional devices.")
                r = self.session.get(config.API_BASE_URI + '?_page=' + str(page)).json()
                if 'code' in r:
                    raise config.DattoApiError("Error querying Datto API for second page of devices")
                devices.extend(r['items'])

        devices = sorted(devices, key= lambda i: i['name'].upper()) # let's sort this bad boy!
        return devices

    @retry(config.DattoApiError, tries=3, delay=3, logger=logging.getLogger())
    def getAssetDetails(self,serialNumber):
        """
        With a device serial number (argument), query the API with it
        to retrieve JSON data with the asset info for that device.

        Returns JSON data (dictionary) for the device with the given serial number
        """

        self.logger.debug("Querying API for device asset details.")
        asset_data = self.session.get(config.API_BASE_URI + '/' + serialNumber + '/asset').json()

        if 'code' in asset_data:
            raise config.DattoApiError(f'Error encountered retrieving asset details for "{serialNumber}"'))

        return asset_data

    def rebuildScreenshotUrl(self,url):
        '''Rebuild the URL using the new images URL.'''

        baseUrl = 'https://device.dattobackup.com/sirisReporting/images/latest'

        o = urlparse(url)
        imageName = o.query.split('/')[-1]
        newUrl = '/'.join([baseUrl, imageName])

        return newUrl

    def getAgentScreenshot(self,deviceName,agentName):
        """Search the XML API output for a screenshot URL for the device & agent.

        Returns:  the screenshot URL as well as the error message and/or OCR.
        """

        self.logger.debug(f"Retrieving screenshot URL for '{agentName}' on '{deviceName}'")
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

        self.logger.info('Closing requests session')
        return self.session.close()

class DattoCheck():
    "Handles the main functions of the script."

    def __init__(self, args):
        "Constructor - initialize the \"Datto\" class to handle API communications."

        self.args = args

        # initialize results_data, used for generating html report
        self.results_data = {'critical' : [],
                        'backup_error' : [],
                        'offsite_error' : [],
                        'screenshot_error' : [],
                        'verification_error' : [],
                        'informational' : []
                        }

        self.setupLogging()
        self.datto = Datto(args.AUTH_USER, args.AUTH_PASS, args.XML_API_KEY)
        self.devices = self.datto.getDevices()

    def setupLogging(self):
        "Configure rotating log to file and optional stdout log stream."

        # Add rotating log
        self.logger = logging.getLogger("Datto Check")
        self.logger.setLevel(logging.DEBUG)
        handler = RotatingFileHandler(config.LOG_FILE, maxBytes=30000, backupCount=3)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        # If verbose is set, add stdout logging handler
        if self.args.verbose:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        return

    def display_time(self, seconds, granularity=2):
        """
        Converts an integer (number of seconds) into a readable time format \
        with certain granularity.

        From "Mr. B":
        https://stackoverflow.com/questions/4048651/python-function-to-convert-seconds-into-minutes-hours-and-days/24542445#answer-24542445
        """
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


    def buildMessageBody(self):
        "Wrapper function for buildHtmlEmail()"

        try:
            MSG_BODY = self.buildHtmlEmail(self.results_data).strip('\n')
        except Exception as e:
            self.logger.error('Failed to build email body')
            MSG_BODY = '<pre>\nFailed to build HTML email report.  This was likely caused by the API returning corrupt (or empty) data for a device.<br><br>'
            MSG_BODY += 'Error & Traceback:<br><br>"{}"<br>{}</pre>'.format(str(e), traceback.format_exc())
        return MSG_BODY

    def email_report(self):
        """Email error report to listed recipients.

        If using Office 365 and only sending to recipients in the
        same domain, it's best to use the "direct send" method because
        authentication is not required. See Option 2 here (you'll need a send connector for this):

        https://docs.microsoft.com/en-us/exchange/mail-flow-best-practices/how-to-set-up-a-multifunction-device-or-application-to-send-email-using-office-3
        """

        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        self.logger.info("Sending email report to: {}".format(self.args.email_to))
        d = datetime.datetime.today()

        # Email heads
        msg = MIMEMultipart()
        msg['Subject'] = 'Daily Datto Check: {}'.format(d.strftime('%m/%d/%Y'))
        msg['From'] = self.args.email_from
        msg['To'] = ', '.join(self.args.email_to)
        if self.args.email_cc:
            msg['Cc'] = ', '.join(self.args.email_cc)
        body = self.buildMessageBody()
        msg.attach(MIMEText(body, 'html'))

        # Send email
        s = smtplib.SMTP(host=self.args.mx_endpoint, port=self.args.smtp_port)

        try:
            if self.args.starttls:
                s.starttls()
            if self.args.email_pw:
                s.login(self.args.email_from, self.args.email_pw)
            s.send_message(msg)
            s.quit()
        except Exception as e:
            self.logger.critical(f"Failed to send email message!\n  {str(e)}")
            pass
        return

    def checkActiveTickets(self, device):
        "Check whether the device has any active tickets open."

        if device['activeTickets']:
            error_text = 'Appliance has {} active {}'.format(\
                device['activeTickets'], 'ticket' if device['activeTickets'] < 2 else 'tickets' )
            self.appendError(['informational', device['name'], 'N/A', error_text])
            self.logger.debug(f"{device['name']}: {error_text}")
        return

    def checkLastCheckin(self, device):
        "Checks the last time the device checked in to the Datto Portal."

        t = device['lastSeenDate'][:22] + device['lastSeenDate'][23:] # remove the colon from time zone
        device_checkin = datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%S%z")
        now = datetime.datetime.now(datetime.timezone.utc) # make 'now' timezone aware
        timeDiff = now - device_checkin

        if timeDiff.total_seconds() >= config.CHECKIN_LIMIT:
            error_text = "Last checkin was {} ago.".format(self.display_time(timeDiff.total_seconds()))
            self.appendError(['critical', device['name'], 'Appliance Offline', error_text])
            self.logger.debug(f"{device['name']}: Appliance Offline")
            return  # do not proceed if the device is offline; go to next device
        return

    def checkDiskUsage(self, device):
        "Check disk usage reported by the API and calculate percentages"

        storage_available = int(device['localStorageAvailable']['size'])
        storage_used = int(device['localStorageUsed']['size'])
        total_space = storage_available + storage_used
        try:
            available_pct = float("{0:.2f}".format(storage_used / total_space)) * 100
        except ZeroDivisionError as e:
            self.logger.error('"{}" calculating free space (API returned null value) on device: "{}"'.format(str(e),device['name']))
            return

        if available_pct > config.STORAGE_PCT_THRESHOLD:
            error_text = 'Local storage exceeds {}%.  Current Usage: {}%'.\
                        format(str(config.STORAGE_PCT_THRESHOLD), str(available_pct))
            self.appendError(['critical', device['name'], 'Low Disk Space',error_text])
            self.logger.debug(f"{device['name']}: {error_text}")
        return

    def deviceChecks(self,device):
        """Performs device checks on an \"asset\" object retrieved from the API.

        Calls self.agentChecks() for the device passed.
        """

        self.logger.debug(f" --- Starting device and agent checks for '{device['name']}' ---")

        if device['hidden']:
            self.logger.debug(f"Skipping hidden asset: {device['name']}.")
            return
        if device['name'] == 'backupDevice': 
            return

        self.checkActiveTickets(device)
        self.checkLastCheckin(device)
        self.checkDiskUsage(device)

        # Run agent checks
        assetDetails = self.datto.getAssetDetails(device['serialNumber'])
        for agent in assetDetails:
            self.agentChecks(agent, device)
        return

    def agentChecks(self, agent, device):
        "Perform agent checks"

        try:
            if agent['isArchived']:
                self.logger.debug(f"Agent {agent['name']} is archived.")
                return
            if agent['isPaused']:
                self.logger.debug(f"Agent {agent['name']} is paused.")
                return
        except Exception as e:
            self.logger.critical('"{}" (device: "{}")'.format(str(e), device['name']))
            return

        BACKUP_FAILURE = False

        # check if the most recent backup was more than LAST_BACKUP_THRESHOLD
        lastBackupTime = datetime.datetime.fromtimestamp(agent['lastSnapshot'], datetime.timezone.utc)
        now = datetime.datetime.now(datetime.timezone.utc)
        timeDiff = now - lastBackupTime

        if timeDiff.total_seconds() > config.LAST_BACKUP_THRESHOLD:
            try:
                if agent['backups'][0]['backup']['status'] != 'success':  # only error if the last scheduled backup failed
                    backup_error = agent['backups'][0]['backup']['errorMessage']
                    if not backup_error:
                        backup_error = "No error message available"
                    # if local backups exist, get last successful backup time
                    if agent['lastSnapshot']:
                        lastSnapshotTime = str(self.display_time(timeDiff.total_seconds())) + ' ago'
                    else:
                        lastSnapshotTime = "(no local snapshots exist)"
                    error_text = '-- "{}": Last scheduled backup failed; last backup was: {}. Error: "{}"'.format(\
                        agent['name'], lastSnapshotTime, backup_error)

                    BACKUP_FAILURE = True
                    errorData = ['backup_error', device['name'], agent['name'],'{}'.format(lastSnapshotTime), backup_error]

                    if timeDiff.total_seconds() > config.ACTIONABLE_THRESHOLD and agent['lastSnapshot']:
                        self.appendError(errorData, color='red')
                    else:
                        self.appendError(errorData)
                    self.logger.debug(error_text)

            except IndexError:
                error_text = 'Agent does not seem to have any backups'
                self.logger.debug(f"Agent {agent['name']} does not seem to have any backups.")
                self.appendError(['informational', device['name'], agent['name'], error_text])

        # Check if latest off-site point exceeds LAST_OFFSITE_THRESHOLD
        if not agent['latestOffsite']:
            error_text = 'No off-site backup points exist'
            self.appendError(['informational', device['name'], agent['name'], error_text])
            self.logger.debug(f"{agent['name']} - {error_text}")
        elif not BACKUP_FAILURE:
            lastOffsite = datetime.datetime.fromtimestamp(agent['latestOffsite'], datetime.timezone.utc)
            timeDiff = now - lastOffsite
            if timeDiff.total_seconds() > config.LAST_OFFSITE_THRESHOLD:
                error_text = 'Last off-site: {} ago'.format(self.display_time(timeDiff.total_seconds()))
                if timeDiff.total_seconds() > config.ACTIONABLE_THRESHOLD:
                    self.appendError(['offsite_error', device['name'], agent['name'], error_text], 'red')
                else:
                    self.appendError(['offsite_error', device['name'], agent['name'], error_text])
                self.logger.debug(f"{agent['name']} - {error_text}")

        # check if time of latest screenshot exceeds LAST_SCREENSHOT_THRESHOLD
        if agent['type'] == 'agent' and agent['lastScreenshotAttempt'] and not BACKUP_FAILURE:
            last_screenshot = datetime.datetime.fromtimestamp(agent['lastScreenshotAttempt'], datetime.timezone.utc)
            timeDiff = now - last_screenshot
            if timeDiff.total_seconds() > config.LAST_SCREENSHOT_THRESHOLD:
                error_text = 'Last screenshot was {} ago.'.format(display_time(timeDiff.total_seconds()))
                if timeDiff.total_seconds() > config.ACTIONABLE_THRESHOLD:
                    self.appendError(['screenshot_error', device['name'], agent['name'], error_text, '', 'red'])
                else:
                    self.appendError(['screenshot_error', device['name'], agent['name'], error_text, ''])
                self.logger.debug(f"{agent['name']} - {error_text}")

        # check status of last screenshot attempt
        if not BACKUP_FAILURE and agent['type'] == 'agent' and agent['lastScreenshotAttemptStatus'] == False:
            error_text = 'Last screenshot attempt failed!'
            screenshotURI,screenshotErrorMessage = self.datto.getAgentScreenshot(device['name'], agent['name'])
            if screenshotURI == -1:
                screenshotURI = ""
                screenshotErrorMessage = ""
            self.appendError(['screenshot_error', device['name'], agent['name'], screenshotURI, screenshotErrorMessage])
            self.logger.debug(f"{agent['name']} - {error_text}")

        # check local verification and report any errors
        try:
            if not BACKUP_FAILURE and agent['type'] == 'agent' and agent['backups'] and agent['backups'][0]['localVerification']['errors']:
                for error in agent['backups'][0]['localVerification']['errors']:
                    error_text = 'Local Verification Failure!\n{}\n{}'.format(error['errorType'],error['errorMessage'])
                    self.appendError(['verification_error', device['name'], agent['name'], error['errorType'], error['errorMessage']])
                    self.logger.debug(f"{agent['name']} - {error_text}")
        except Exception as e:
            self.logger.error('Device: "{}" Agent: "{}". {}'.format(device['name'], agent['name'], str(e)))
        return

    def buildHtmlEmail(self, results_data):
        """Compile all results into HTML tables based on error level."""

        self.logger.info('Building HTML email message body.')
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

    def appendError(self, error_detail, color=None):
        """Append an error to the results_data list.

            error_detail - List of error data.
                First and second items are error level, and device name
        """

        if color: error_detail.append(color)
        self.results_data[error_detail[0]].append(error_detail)
        return

    def run(self):
        "Run Datto Check functions."

        self.logger.info("Starting Datto Check Script")

        for device in self.devices:
            self.deviceChecks(device)

        if self.args.send_email:
            self.email_report()

        self.datto.sessionClose()
        self.logger.info("Datto check script complete.")
        return
