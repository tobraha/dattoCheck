"""Datto API

This module contains the Datto 'Api' object, which
handles communication with the Datto API.
"""

# Imports: Standard
import logging
import sys
import traceback
from urllib.parse import urlparse
from html import escape
from xml.etree import ElementTree as ET
import requests
from retry import retry

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

    def __init__(self):
        '''Constructor - initialize Python Requests Session and get XML API data'''

        logger.info('Creating new Python requests session with the API endpoint.')
        self.session = requests.Session()
        self.session.auth = (config.AUTH_USER, config.AUTH_PASS)
        self.session.headers.update({"Content-Type": "application/json"})

        self.xml_api_root = self.get_xml_api_data(config.AUTH_XML)

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
            # TODO: send an email!
            sys.exit(-1)

    @retry(DattoApiError, tries=3, delay=3, logger=logger)
    def get_devices(self):
        "Query API assets target to return all Datto Assets"

        devices = []
        logger.info('Gathering devices info from API')
        assets = self.session.get(config.API_BASE_URI + '?_page=1').json()
        if 'code' in assets:
            logger.fatal('Cannot retrieve devices from API endpoint')
            sys.exit(-1)
        devices.extend(assets['items'])
        total_pages = assets['pagination']['totalPages']
        device_count = assets['pagination']['count']
        logger.debug('API returned %s devices', device_count)

        # new request for each page; extend additional 'items' to devices list
        if total_pages > 1:
            for page in range(2, total_pages+1):
                logger.debug("Querying API for additional devices.")
                assets = self.session.get(config.API_BASE_URI + '?_page=' + str(page)).json()
                if 'code' in assets:
                    raise DattoApiError('Error querying Datto API for additional devices')
                devices.extend(assets['items'])

        # let's sort this thing!
        devices = sorted(devices, key=lambda i: i['name'].upper())
        return devices

    @retry(DattoApiError, tries=3, delay=4, logger=logger)
    def get_asset_details(self, serial_number):
        """
        With a device serial number (argument), query the API with it
        to retrieve JSON data with the asset info for that device.

        Returns JSON data (dictionary) for the device with the given serial number
        """

        logger.debug(" " * 8 + "Querying API for device asset details.")
        asset_data = self.session.get(config.API_BASE_URI + '/' + serial_number + '/asset').json()

        if 'code' in asset_data:
            raise DattoApiError(f'    Failed to get asset details from API')

        return asset_data

    def get_agent_screenshot(self, device, agent):
        """Search the XML API output for a screenshot URL for the device & agent.

        Returns:  the screenshot as an HTML element
        """

        logger.debug(" " * 8 + "Retrieving agent screenshot")
        # Find 'Device' elements.  If it matches, find the target agent and get screenshot URI.
        for xml_device in self.xml_api_root.findall('Device'):

            # Iterate through devices to find the target device
            xml_hostname = xml_device.find('Hostname')
            if xml_hostname.text == device:

                # Iterate through device agents to find target agent
                backup_volumes = xml_device.find('BackupVolumes')
                for backup_volume in backup_volumes.findall('BackupVolume'):
                    xml_agent_name = backup_volume.find('Volume')

                    # If agent name matches, get screenshot URI and return
                    if xml_agent_name.text == agent:
                        uri = backup_volume.find('ScreenshotImagePath').text

                        # check to see if the old API is being used; correct if so
                        if 'partners.dattobackup.com' in uri:
                            uri = self.rebuild_screenshot_url(uri)

                        if backup_volume.find('ScreenshotError').text:
                            error = escape(backup_volume.find('ScreenshotError').text)
                        else:
                            error = "[error message not available]"
                        screenshot = f'<a href="{uri}"><img src="{uri}" alt="" width="160" title="{error}"></img></a>'
                        return screenshot
        return(-1)

    def rebuild_screenshot_url(self, url):
        '''Rebuild the URL using the new images URL'''

        base_url = 'https://device.dattobackup.com/sirisReporting/images/latest'
        url_parsed = urlparse(url)
        image_name = url_parsed.query.split('/')[-1]
        new_url = '/'.join([base_url, image_name])
        return new_url

    def session_close(self):
        """Close the "requests" session"""

        return self.session.close()
