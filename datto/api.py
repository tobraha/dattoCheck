# Datto API
#
# This module contains the Datto 'Api' object, which
# handles communication with the Datto API.

# Imports: Standard
import logging
import requests
import sys
from retry import retry
from xml.etree import ElementTree as ET

# Import: local
import config

# global logger
logger = logging.getLogger("Datto Check")

class DattoApiError(Exception):
	"""Raised on errors encountered from the Datto API."""
	pass


class Api():
    """Datto API
    
    Handles the communication with the Datto API.
    """

    @retry(config.DattoApiError, tries=3, delay=3)
    def test_api_connection(self):
        """Make a connection to the API Base URL to test connectivity and credentials.
        Store the initial device query for later use.
        """

        logger.info("Retrieving initial asset list.")
        self.assets = self.session.get(config.API_BASE_URI + '?_page=1').json()
        logger.info('API returned a total of %s devices', self.assets['pagination']['count'])
        if 'code' in self.assets:
            logger.fatal("Error querying API for devices!")
            sys.exit(-1)

    def get_xml_api_data(self, xml_key):
        """Retrieve and parse data from XML API
        Returns xml ElementTree of Datto XML content"""

        logger.info('Retrieving Datto XML API data.')
        xml_request = requests.Session()
        xml_request.headers.update({"Content-Type": "text/xml"})
        url = config.XML_API_BASE_URI + '/' + xml_key
        api_xml_data = xml_request.get(url).text.replace(u"\u000C", "")
        xml_request.close()
        try:
            xml_parsed = ET.fromstring(api_xml_data)
            return xml_parsed
        except ET.ParseError as exception:
            logger.fatal("Failure parsing XML from Datto API!")
            trace = traceback.format_exc().replace('\n', '<br>')
            email_body = "<h1>A fatal error occurred:</h1>"
            email_body += "<h2>Failed to parse XML from Datto API</h2>"
            email_body += '<h3>{0}</h3><br><pre>{1}</pre>'.format(str(exception), trace)
            email_report(self.args, body=email_body)
            sys.exit(-1)

    @retry(DattoApiError, tries=3, delay=3)
    def get_devices(self):
        """
        Use the initial device API query to load all devices
         -Check pagination details and iterate through any additional pages
          to return a list of all devices
        Returns a list of all 'items' from the devices API.
        """

        # load the first (up to) 100 devices into device list
        # get total number of pages
        devices = []
        devices.extend(self.assets['items'])
        total_pages = self.assets['pagination']['totalPages']

        # new request for each page; extend additional 'items' to devices list
        if total_pages > 1:
            for page in range(2, total_pages+1):
                logger.info("Querying API for additional devices.")
                result = self.session.get(config.API_BASE_URI + '?_page=' + str(page)).json()
                if 'code' in result:
                    raise config.DattoApiError("Error querying Datto API for \
                    additional devices")
                devices.extend(result['items'])

        # let's sort this thing!
        devices = sorted(devices, key=lambda i: i['name'].upper())
        return devices

    @retry(DattoApiError, tries=3, delay=3)
    def get_asset_details(self, serial_number):
        """
        With a device serial number (argument), query the API with it
        to retrieve JSON data with the asset info for that device.

        Returns JSON data (dictionary) for the device with the given serial number
        """

        logger.debug("Querying API for device asset details.")
        asset_data = self.session.get(config.API_BASE_URI + '/' + serial_number + '/asset').json()

        if 'code' in asset_data:
            raise config.DattoApiError(f'Error encountered retrieving \
            asset details for "{serial_number}"')

        return asset_data

    def get_agent_screenshot(self, device_name, agent_name):
        """Search the XML API output for a screenshot URL for the device & agent.

        Returns:  the screenshot URL as well as the error message and/or OCR.
        """

        logger.debug("Retrieving screenshot URL for %s on %s", agent_name, device_name)
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