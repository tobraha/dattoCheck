

import config

class Datto:
    """
    Handles the session and communication with the Datto API.
    """
    def __init__(self):
        '''Constructor - initialize Python Requests Session and get XML API data'''
        # create intial session and set parameters
        logger.info('Creating new python requests session with the API endpoint.')
        self.session = requests.Session()
        self.session.auth = (config.AUTH_USER, config.AUTH_PASS)
        self.session.headers.update({"Content-Type" : "application/json"})

        self.test_api_connection()
        self.xml_api_root = self.get_xml_api_data()

    @retry(DattoApiError, tries=3, delay=3, logger=logger)
    def test_api_connection(self):
        """Make a connection to the API Base URL to test connectivity and credentials.
        Store the initial device query for later use.
        """
        logger.info("Retrieving initial asset list.")
        self.assets = self.session.get(config.API_BASE_URI + '?_page=1').json()
        if 'code' in self.assets:
            raise DattoApiError("Error querying API for devices")
        return

    def get_xml_api_data(self):
        '''Retrieve and parse data from XML API
        Returns xml ElementTree of Datto XML content'''
        logger.info('Retrieving Datto XML API data.')
        xml_request = requests.Session()
        xml_request.headers.update({"Content-Type" : "application/xml"})
        api_xml_data = xml_request.get(config.XML_API_URI).text
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
                r = self.session.get(config.API_BASE_URI + '?_page=' + str(page)).json()
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
        asset_data = self.session.get(config.API_BASE_URI + '/' + serialNumber + '/asset').json()

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
