# Datto
#
# Handles control of the program flow.

# Import: standard
import logging
from datetime import datetime

# Import: local
import config
from mail import Email
from datto.api import Api
from datto.device import Device
from datto.agent import Agent

logger = logging.getLogger("Datto Check")


class DattoCheck():
    "Handles the main functions of the script."

    def __init__(self, include_unprotected):
        """Constructor"""

        self.api = Api()
        self.results = Results()
        self.include_unprotected = include_unprotected

    def run(self):
        """Run device and agent checks"""

        # Main loop
        devices = self.api.get_devices()
        for device in devices:

            # Begin
            device = Device(device, self.results)
            logger.debug('---- Device: %s ----', device.name)

            # Device checks
            if device.is_inactive():
                logger.debug('    Device is archived or paused')
                continue
            device.run_device_checks()
            if device.is_offline:
                logger.debug('    Device is offline; skipping remaining checks')
                continue

            # Agent checks
            asset_details = self.api.get_asset_details(device.serial_number)
            for agent in asset_details:
                agent = Agent(self.api,
                              agent,
                              device,
                              self.results,
                              self.include_unprotected)
                logger.debug('    ---- Agent: %s ----', agent.name)
                if agent.is_inactive():
                    logger.debug(' ' * 8 + 'Agent is archived or paused')
                    continue
                agent.run_agent_checks()
        self.api.session_close()
        logger.info('All checks complete')

        # Main loop done; send report
        if config.EMAIL_TO:
            mailer = Email()

            d = datetime.today()
            subject = 'Daily Datto Check: {}'.format(d.strftime('%m/%d/%Y'))

            report = mailer.build_html_report(self.results.results)
            mailer.send_email(config.EMAIL_TO, config.EMAIL_FROM, subject, report, config.EMAIL_CC)


class Results():

    def __init__(self):
        "Constructor"
        # initialize results_data, used for generating html report
        self.results = {'critical':
                            {
                            'name': "CRITICAL ERRORS",
                            'columns': ['Appliance', 'Error Type', 'Error Details'],
                            'errors': []
                            },
                        'backup_error':
                            {
                            'name': "Backup Errors",
                            'columns': ['Appliance', 'Agent/Share', 'Last Backup', 'Error Details'],
                            'errors': []
                            },
                        'offsite_error':
                            {
                            'name': 'Off-site Sync Issues',
                            'columns': ['Appliance', 'Agent/Share', 'Error Details'],
                            'errors': []
                            },
                        'screenshot_error':
                            {
                            'name': 'Screenshot Failures',
                            'columns': ['Appliance', 'Agent', 'Screenshot/Details'],
                            'errors': []
                            },
                        'verification_error':
                            {
                            'name': 'Local Verification Issues',
                            'columns': ['Appliance', 'Agent', 'Error', 'Details'],
                            'errors': []
                            },
                        'informational':
                            {
                            'name': 'Informational',
                            'columns': ['Appliance', 'Agent/Share', 'Details'],
                            'errors': []
                            }
                        }

    def append_error(self, error_detail, color=None):
        """Append an error to the results_data list.

            error_detail - List of error data.
                First and second items are error level, and device name
        """

        if color:
            error_detail.append(color)

        self.results[error_detail[0]]['errors'].append(error_detail)

