import logging
import datetime
import traceback
import sys

# Import: Others
from urllib.parse import urlparse
from logging.handlers import RotatingFileHandler
from xml.etree import ElementTree as ET
from retry import retry
import requests
import config

# Internal Imports
from .base import DattoAsset

class Datto():
    """
    Handles the session and communication with the Datto API.
    """
    def __init__(self, user, password, xml_key):
        '''Constructor - initialize Python Requests Session and get XML API data'''

        self.logger = logging.getLogger("Datto Check")
        self.logger.info('Creating new Python requests session with the API endpoint.')
        self.session = requests.Session()
        self.session.auth = (user, password)
        self.session.headers.update({"Content-Type" : "application/json"})

        self.test_api_connection()
        self.xml_api_root = self.get_xml_api_data(xml_key)

    @retry(config.DattoApiError, tries=3, delay=3)
    def test_api_connection(self):
        """Make a connection to the API Base URL to test connectivity and credentials.
        Store the initial device query for later use.
        """

        self.logger.info("Retrieving initial asset list.")
        self.assets = self.session.get(config.API_BASE_URI + '?_page=1').json()
        if 'code' in self.assets:
            raise config.DattoApiError("Error querying API for devices")


    def get_xml_api_data(self, xml_key):
        """Retrieve and parse data from XML API
        Returns xml ElementTree of Datto XML content"""

        self.logger.info('Retrieving Datto XML API data.')
        xml_request = requests.Session()
        xml_request.headers.update({"Content-Type" : "application/xml"})
        url = config.XML_API_BASE_URI + '/' + xml_key
        api_xml_data = xml_request.get(url).text
        xml_request.close()
        return ET.fromstring(api_xml_data)

    @retry(config.DattoApiError, tries=3, delay=3)
    def get_devices(self):
        """
        Use the initial device API query to load all devices
         -Check pagination details and iterate through any additional pages
          to return a list of all devices
        Returns a list of all 'items' from the devices API.
        """

        devices = []
        devices.extend(self.assets['items']) # load the first (up to) 100 devices into device list
        total_pages = self.assets['pagination']['totalPages'] # see how many pages there are

        # new request for each page; extend additional 'items' to devices list
        if total_pages > 1:
            for page in range(2, total_pages+1):
                self.logger.info("Querying API for additional devices.")
                result = self.session.get(config.API_BASE_URI + '?_page=' + str(page)).json()
                if 'code' in result:
                    raise config.DattoApiError("Error querying Datto API for \
                    second page of devices")
                devices.extend(result['items'])

        devices = sorted(devices, key=lambda i: i['name'].upper()) # let's sort this bad boy!
        return devices

    @retry(config.DattoApiError, tries=3, delay=3)
    def get_asset_details(self, serial_number):
        """
        With a device serial number (argument), query the API with it
        to retrieve JSON data with the asset info for that device.

        Returns JSON data (dictionary) for the device with the given serial number
        """

        self.logger.debug("Querying API for device asset details.")
        asset_data = self.session.get(config.API_BASE_URI + '/' + serial_number + '/asset').json()

        if 'code' in asset_data:
            raise config.DattoApiError(f'Error encountered retrieving \
            asset details for "{serial_number}"')

        return asset_data


    def get_agent_screenshot(self, device_name, agent_name):
        """Search the XML API output for a screenshot URL for the device & agent.

        Returns:  the screenshot URL as well as the error message and/or OCR.
        """

        self.logger.debug("Retrieving screenshot URL for %s on %s", agent_name, device_name)
        # Find 'Device' elements.  If it matches, find the target agent and get screenshot URI.
        for xml_device in self.xml_api_root.findall('Device'):

            # Iterate through devices to find the target device
            xml_hostname = xml_device.find('Hostname')
            if xml_hostname.text == device_name:

                # Iterate through device agents to find target agent
                backup_volumes = xml_device.find('BackupVolumes')
                for backup_volume in backup_volumes.findall('BackupVolume'):
                    xml_agent_name = backup_volume.find('Volume')

                    # If agent name matches, get screenshot URI and return
                    if xml_agent_name.text == agent_name:
                        screenshot_uri = ""
                        screenshot_uri = backup_volume.find('ScreenshotImagePath').text

                        #check to see if the old API is being used; correct if so
                        if 'partners.dattobackup.com' in screenshot_uri:
                            screenshot_uri = rebuild_screenshot_url(screenshot_uri)

                        if backup_volume.find('ScreenshotError').text:
                            screenshot_error_message = backup_volume.find('ScreenshotError').text
                        else:
                            screenshot_error_message = "[error message not available]"
                        return screenshot_uri, screenshot_error_message
        return(-1, -1)

    def session_close(self):
        """Close the "requests" session"""

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

        self.setup_logging()
        self.logger.info("Starting Datto Check Script")
        self.datto = Datto(args.AUTH_USER, args.AUTH_PASS, args.XML_API_KEY)
        self.devices = self.datto.get_devices()

    def setup_logging(self):
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


    def build_message_body(self):
        "Wrapper function for buildHtmlEmail()"

        try:
            msg_body = self.build_html_email(self.results_data).strip('\n')
        except Exception as e:
            self.logger.error('Failed to build email body')
            msg_body = '<pre>\nFailed to build HTML email report. This was likely caused by the API returning corrupt (or empty) data for a device.<br><br>'
            msg_body += 'Error & Traceback:<br><br>"{}"<br>{}</pre>'.format(str(e), traceback.format_exc())
        return msg_body

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

        self.logger.info("Preparing and sending email report to: {}".format(self.args.email_to))
        d = datetime.datetime.today()

        # Email heads
        msg = MIMEMultipart()
        msg['Subject'] = 'Daily Datto Check: {}'.format(d.strftime('%m/%d/%Y'))
        msg['From'] = self.args.email_from
        msg['To'] = ', '.join(self.args.email_to)
        if self.args.email_cc:
            msg['Cc'] = ', '.join(self.args.email_cc)
        body = self.build_message_body()
        msg.attach(MIMEText(body, 'html'))

        # Send email
        s = smtplib.SMTP(host=self.args.mx_endpoint, port=int(self.args.smtp_port))

        try:
            if self.args.starttls:
                s.starttls()
            if self.args.email_pw:
                s.login(self.args.email_from, self.args.email_pw)
            s.send_message(msg)
            s.quit()
            self.logger.info("Email report sent.")
        except Exception as e:
            self.logger.critical("Failed to send email message:\n  %s", str(e))


    def check_active_tickets(self, device):
        "Check whether the device has any active tickets open."

        if device['activeTickets']:
            error_text = 'Appliance has {} active {}'.format(\
                device['activeTickets'], 'ticket' if device['activeTickets'] < 2 else 'tickets' )
            self.append_error(['informational', device['name'], 'N/A', error_text])
            self.logger.debug("%s:  %s", device['name'], error_text)


    def checkLastCheckin(self, device):
        "Checks the last time the device checked in to the Datto Portal."

        time_string = device['lastSeenDate'][:22] + device['lastSeenDate'][23:] # remove the colon from time zone
        device_checkin = datetime.datetime.strptime(time_string,
                                                    "%Y-%m-%dT%H:%M:%S%z")
        now = datetime.datetime.now(datetime.timezone.utc) # make 'now' timezone aware
        time_diff = now - device_checkin

        if time_diff.total_seconds() >= config.CHECKIN_LIMIT:
            error_text = "Last checkin was {} ago.".format(display_time(time_diff.total_seconds()))
            self.append_error(['critical', device['name'], 'Appliance Offline', error_text])
            self.logger.debug(f"{device['name']}: Appliance Offline")
            return  # do not proceed if the device is offline; go to next device


    def check_disk_usage(self, device):
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
            self.append_error(['critical', device['name'], 'Low Disk Space', error_text])
            self.logger.debug("%s:  %s", device['name'], error_text)


    def deviceChecks(self,device):
        """Performs device checks on an "asset" object retrieved from the API.

        Calls self.agentChecks() for the device passed.
        """

        self.logger.debug(f" --- Starting device and agent checks for '{device['name']}' ---")

        if device['hidden']:
            self.logger.debug(f"Skipping hidden asset: {device['name']}.")
            return
        if device['name'] == 'backupDevice': 
            return

        self.check_active_tickets(device)
        self.checkLastCheckin(device)
        self.check_disk_usage(device)

        # Run agent checks
        assetDetails = self.datto.get_asset_details(device['serialNumber'])
        for agent in assetDetails:
            agent = DattoAsset(agent)
            self.agent_checks(agent, device)
        return

    def agent_checks(self, agent, device):
        "Perform agent checks"

        try:
            if agent.is_archived:
                self.logger.debug(f"Agent {agent.name} is archived.")
                return
            if agent.is_paused:
                self.logger.debug(f"Agent {agent.name} is paused.")
                return
        except Exception as e:
            self.logger.critical('"{}" (device: "{}")'.format(str(e), device['name']))
            return

        BACKUP_FAILURE = False

        # check if the most recent backup was more than LAST_BACKUP_THRESHOLD
        last_backup_time = datetime.datetime.fromtimestamp(agent.last_snapshot, datetime.timezone.utc)
        now = datetime.datetime.now(datetime.timezone.utc)
        time_diff = now - last_backup_time

        if time_diff.total_seconds() > config.LAST_BACKUP_THRESHOLD:
            try:
                if agent.backups[0]['backup']['status'] != 'success':  # only error if the last scheduled backup failed
                    backup_error = agent.backups[0]['backup']['errorMessage']
                    if not backup_error:
                        backup_error = "No error message available"
                    # if local backups exist, get last successful backup time
                    if agent.last_snapshot:
                        last_snapshot_time = str(display_time(time_diff.total_seconds())) + ' ago'
                    else:
                        last_snapshot_time = "(no local snapshots exist)"
                    error_text = '-- "{}": Last scheduled backup failed; last \
                    backup was: {}. Error: "{}"'.format(agent.name,
                                                        last_snapshot_time,
                                                        backup_error)

                    BACKUP_FAILURE = True
                    errorData = ['backup_error',
                                 device['name'],
                                 agent.name, '{}'.format(last_snapshot_time), backup_error]

                    if time_diff.total_seconds() > config.ACTIONABLE_THRESHOLD and agent.last_snapshot:
                        self.append_error(errorData, color='red')
                    else:
                        self.append_error(errorData)
                    self.logger.debug(error_text)

            except IndexError:
                error_text = 'Agent does not seem to have any backups'
                self.logger.debug("Agent %s does not seem to have any backups.", agent.name)
                self.append_error(['informational', device['name'], agent.name, error_text])

        # Check if latest off-site point exceeds LAST_OFFSITE_THRESHOLD
        if not agent.latest_offsite:
            error_text = 'No off-site backup points exist'
            self.append_error(['informational', device['name'], agent.name, error_text])
            self.logger.debug("%s - %s", agent.name, error_text)
        elif not BACKUP_FAILURE:
            last_offsite = datetime.datetime.fromtimestamp(agent.latest_offsite, datetime.timezone.utc)
            time_diff = now - last_offsite
            if time_diff.total_seconds() > config.LAST_OFFSITE_THRESHOLD:
                error_text = 'Last off-site: {} ago'.format(display_time(time_diff.total_seconds()))
                if time_diff.total_seconds() > config.ACTIONABLE_THRESHOLD:
                    self.append_error(['offsite_error',
                                      device['name'],
                                      agent.name,
                                      error_text],
                                     'red')
                else:
                    self.append_error(['offsite_error', device['name'], agent.name, error_text])
                self.logger.debug("%s - %s", agent.name, error_text)

        # check if time of latest screenshot exceeds LAST_SCREENSHOT_THRESHOLD
        if agent.type == 'agent' and agent.last_screenshot_attempt and not BACKUP_FAILURE:
            last_screenshot = datetime.datetime.fromtimestamp(agent.last_screenshot_attempt,
                                                              datetime.timezone.utc)
            time_diff = now - last_screenshot
            if time_diff.total_seconds() > config.LAST_SCREENSHOT_THRESHOLD:
                error_text = 'Last screenshot was {} ago.'.format(display_time(time_diff.total_seconds()))
                if time_diff.total_seconds() > config.ACTIONABLE_THRESHOLD:
                    self.append_error(['screenshot_error', device['name'],
                                      agent.name, error_text, '', 'red'])
                else:
                    self.append_error(['screenshot_error', device['name'],
                                      agent.name, error_text, ''])
                self.logger.debug("%s - %s", agent.name, error_text)

        # check status of last screenshot attempt
        if not BACKUP_FAILURE and agent.type == 'agent' and not agent.last_screenshot_attempt_status:
            error_text = 'Last screenshot attempt failed!'
            screenshot_uri, screenshot_error_message = self.datto.get_agent_screenshot(device['name'],
                                                                                       agent.name)
            if screenshot_uri == -1:
                screenshot_uri = ""
                screenshot_error_message = ""
            self.append_error(['screenshot_error', device['name'], agent.name,
                              screenshot_uri, screenshot_error_message])
            self.logger.debug("%s - %s", agent.name, error_text)

        # check local verification and report any errors
        try:
            if not BACKUP_FAILURE and agent.type == 'agent' and agent.backups and agent.backups[0]['localVerification']['errors']:
                for error in agent.backups[0]['localVerification']['errors']:
                    error_text = 'Local Verification Failure!\n{}\n{}'.format(error['errorType'],error['errorMessage'])
                    self.append_error(['verification_error', device['name'], agent.name, error['errorType'], error['errorMessage']])
                    self.logger.debug("%s - %s", agent.name, error_text)
        except Exception as e:
            self.logger.error('Device: "{}" Agent: "{}". {}'.format(device['name'], agent.name, str(e)))


    def build_html_email(self, results_data):
        """Compile all results into HTML tables based on error level."""

        self.logger.info('Building HTML email message body.')
        # create initial html structure
        msg_body = '<html><head><style>table,th,td{border:1px solid black;border-collapse: collapse; text-align: left;}th{text-align:center;}</style></head><body>'

        if results_data['critical']:
            msg_body += '<h1>CRITICAL ERRORS</h1><table>'
            msg_body += '<tr><th>Appliance</th><th>Error Type</th><th>Error Details</th></tr>'
            for error in results_data['critical']:
                msg_body += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td></tr>'
            msg_body += '</table>'

        if results_data['backup_error']:
            msg_body += '<h1>Backup Errors</h1><table>\
            <tr><th>Appliance</th><th>Agent/Share</th><th>Last Backup</th><th>Error Details</th></tr>'
            for error in results_data['backup_error']:
                if len(error) == 5:
                    msg_body += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td><td>' + error[4] + '</td></tr>'
                else:
                    msg_body += '<tr style="background-color: {0};"><td>'.format(error[5]) + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td><td>' + error[4] + '</td></tr>'
            msg_body += '</table>'

        if results_data['offsite_error']:
            msg_body += '<h1>Off-Site Sync Issues</h1><table>\
            <tr><th>Appliance</th><th>Agent/Share</th><th>Error Details</th></tr>'
            for error in results_data['offsite_error']:
                if len(error) == 4:
                    msg_body += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td></tr>'
                else:
                    msg_body += '<tr style="background-color: {0};"><td>'.format(error[4]) + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td></tr>'
            msg_body += '</table>'

        if results_data['screenshot_error']:
            msg_body += '<h1>Screenshot Failures</h1><table>\
            <tr><th>Appliance</th><th>Agent</th><th>Screenshot</th></tr>'
            for error in results_data['screenshot_error']:
                if not error[3]:
                    col_three = 'No Data'
                elif error[3].startswith('http'):
                    col_three = '<a href="{0}"><img src="{0}" alt="" width="160" title="{1}"></img></a>'.format(error[3], error[4])
                else:
                    col_three = error[3]
                if len(error) == 5:
                    msg_body += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td width="160">' + col_three + '</td></tr>'
                else:
                    msg_body += '<tr style="background-color: {0};"><td>'.format(error[5]) + error[1] + '</td><td>' + error[2] + '</td><td width="160">' + col_three + '</td></tr>'
            msg_body += '</table>'

        if results_data['verification_error']:
            msg_body += '<h1>Local Verification Issues</h1><table>\
            <tr><th>Appliance</th><th>Agent</th><th>Error Type</th><th>Error Message</th></tr>'
            for error in results_data['verification_error']:
                if error[4]:
                    error_message = error[4]
                else:
                    error_message = '<none>'
                msg_body += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td><td>' + error_message + '</td></tr>'
            msg_body += '</table>'

        if results_data['informational']:
            msg_body += '<h1>Informational</h1><table>\
            <tr><th>Appliance</th><th>Agent/Share</th><th>Details</th></tr>'
            for error in results_data['informational']:
                msg_body += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td></tr>'
            msg_body += '</table>'

        msg_body += '</body></html>'
        return(msg_body)

    def append_error(self, error_detail, color=None):
        """Append an error to the results_data list.

            error_detail - List of error data.
                First and second items are error level, and device name
        """

        if color: error_detail.append(color)
        self.results_data[error_detail[0]].append(error_detail)


    def run(self):
        "Run Datto Check functions."

        self.logger.info("Starting device and agent checks.")

        for device in self.devices:
            self.deviceChecks(device)

        self.logger.info("API queries complete; closing Requests session.")
        self.datto.session_close()

        self.logger.info("Device and agent checks complete.")

        if self.args.send_email:
            self.email_report()

        self.logger.info("Datto check script complete.")


def display_time(seconds, granularity=2):
    """
    Converts an integer (number of seconds) into a readable time format with certain granularity.

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


def rebuild_screenshot_url(url):
    '''Rebuild the URL using the new images URL.'''
    base_url = 'https://device.dattobackup.com/sirisReporting/images/latest'
    url_parsed = urlparse(url)
    image_name = url_parsed.query.split('/')[-1]
    new_url = '/'.join([base_url, image_name])
    return new_url
