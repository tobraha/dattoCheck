# Datto
#
# Handles control of the program flow.

# Import: standard
import logging

# Import: local
from datto.api import Api
from datto.device import Device
from datto.agent import Agent

logger = logging.getLogger("Datto Check")

class DattoCheck():
    "Handles the main functions of the script."

    def __init__(self, args):
        """Constructor"""

        super()
        self.api = Api()
        self.results = Results()

    def run(self):
        """Performs device checks on an "asset" object retrieved from the API.

        Calls self.agentChecks() for the device passed.
        """

        # main loop
        devices = self.api.get_devices()
        for device in devices:
            
            # Begin 
            device = Device(device, self.results)
            logger.info('---- %s ----', device.name)

            # Device checks
            if device.is_inactive():
                logger.info('    Device is archived or paused')
            device.run_device_checks()
            if device.is_offline: continue

            # Agent checks
            asset_details = self.api.get_asset_details(device.serial_number)
            for agent in asset_details:
                agent = Agent(agent)
                agent.run_agent_checks()

class Results():

    def __init__(self):
        "Constructor"
        # initialize results_data, used for generating html report
        self.results = {'critical': [],
                             'backup_error': [],
                             'offsite_error': [],
                             'screenshot_error': [],
                             'verification_error': [],
                             'informational': []
                             }

    def append_error(self, error_detail, color=None):
        """Append an error to the results_data list.

            error_detail - List of error data.
                First and second items are error level, and device name
        """

        if color:
            error_detail.append(color)

        self.results[error_detail[0]].append(error_detail)