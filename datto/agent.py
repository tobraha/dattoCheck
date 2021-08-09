# Agent
#
# Class for a Datto Agent Object
# functions and properties pertaining to a Datto Agent

# Import: standard
import logging
from datetime import datetime, timezone
from html import escape

# Import: local
import config
from datto.base import Base

logger = logging.getLogger("Datto Check")

class Agent(Base):
    "Datto Agent"

    def __init__(self, api, agent, device, results, include_unprotected):
        "Constructor"
        super()
        self.include_unprotected = include_unprotected
        self.api = api
        self.results = results
        self.backup_failure = False
        self.device = device

        # agent-specific properties
        self.has_local_backups = True
        self.name = agent['name']
        self.local_ip = agent['localIp']
        self.os = agent['os']
        self.unprotected_volumes = agent['unprotectedVolumeNames']
        self.agent_version = agent['agentVersion']
        self.is_paused = agent['isPaused']
        self.is_archived = agent['isArchived']
        self.latest_offsite = agent['latestOffsite']
        self.last_snapshot = agent['lastSnapshot']
        self.last_screenshot_attempt = agent['lastScreenshotAttempt']
        self.last_screenshot_status = agent['lastScreenshotAttemptStatus']
        self.last_screenshot_url = agent['lastScreenshotUrl']
        self.fqdn = agent['fqdn']
        self.backups = agent['backups']
        self.type = agent['type']
        try:
            self.last_backup = self.backups[0]
            self.last_backup_status = self.last_backup['backup']['status']
            self.last_backup_error = self.last_backup['backup']['errorMessage']
            self.verification_errors = self.last_backup['localVerification']['errors']
        except IndexError:
            error_text = 'Agent does not seem to have any backups'
            logger.debug(' ' * 8 + '%s', error_text)
            self.results.append_error(['informational', self.device.name, self.name, error_text])
            self.has_local_backups = False

    def is_inactive(self):
        """Check agent paused and archive status to determine
        whether or not the agent is active."""
        if self.is_archived or self.is_paused:
            return True
        else:
            return False

    def check_last_backup_time(self):
        """Check if the most recent backup was more
        than LAST_BACKUP_THRESHOLD"""

        last_backup_time = datetime.fromtimestamp(self.last_snapshot, timezone.utc)
        now = datetime.now(timezone.utc)
        time_diff = (now - last_backup_time).total_seconds()

        if time_diff > config.LAST_BACKUP_THRESHOLD and self.last_backup_status != 'success':
            backup_error = self.last_backup_error
            if not backup_error:
                backup_error = "No error message available"

            # if local backups exist, get last successful backup time
            if self.last_snapshot:
                last_snapshot_time = str(self.display_time(time_diff)) + ' ago'
            else:
                last_snapshot_time = "(no local snapshots exist)"
            self.backup_failure = True

            error_data = ['backup_error',
                            self.device.name,
                            self.name,
                            '{}'.format(last_snapshot_time),
                            backup_error]

            if time_diff > config.ACTIONABLE_THRESHOLD and self.last_snapshot:
                self.results.append_error(error_data, color='red')
            else:
                self.results.append_error(error_data)
            logger.debug(' ' * 8 + 'Last scheduled backup at %s has failed (%s)',
                            last_snapshot_time, backup_error)

    def check_last_offsite_time(self):
        "Check if latest off-site point exceeds LAST_OFFSITE_THRESHOLD"

        now = datetime.now(timezone.utc)

        if not self.latest_offsite:
            error_text = 'No off-site backup points exist'
            self.results.append_error(['informational', self.device.name, self.name, error_text])
            logger.debug(' ' * 8 + '%s', error_text)
        elif not self.backup_failure:
            last_offsite = datetime.fromtimestamp(self.latest_offsite, timezone.utc)
            time_diff = (now - last_offsite).total_seconds()
            if time_diff > config.LAST_OFFSITE_THRESHOLD:
                error_text = 'Last off-site: {} ago'.format(self.display_time(time_diff))
                if time_diff > config.ACTIONABLE_THRESHOLD:
                    self.results.append_error(['offsite_error',
                                      self.device.name,
                                      self.name,
                                      error_text],
                                     'red')
                else:
                    self.results.append_error(['offsite_error', self.device.name, self.name, error_text])
                logger.debug(' ' * 8 + '%s', error_text)

    def check_last_screenshot_time(self):
        "Check if time of latest screenshot exceeds LAST_SCREENSHOT_THRESHOLD"

        now = datetime.now(timezone.utc)
        if self.type == 'agent' and self.last_screenshot_attempt and not self.backup_failure:
            last_screenshot = datetime.fromtimestamp(self.last_screenshot_attempt,
                                                              timezone.utc)
            time_diff = (now - last_screenshot).total_seconds()
            if time_diff > config.LAST_SCREENSHOT_THRESHOLD:
                error_text = 'Last screenshot was {} ago.'.format(self.display_time(time_diff))
                if time_diff > config.ACTIONABLE_THRESHOLD:
                    self.results.append_error(['screenshot_error', self.device.name,
                                      self.name, error_text, '', 'red'])
                else:
                    self.results.append_error(['screenshot_error', self.device.name,
                                      self.name, error_text])
                logger.debug(' ' * 8 + '%s', error_text)

    def check_last_screenshot_status(self):
        "Check status of last screenshot attempt"

        if not self.backup_failure and self.type == 'agent' and not self.last_screenshot_status:
            error_text = 'Last screenshot attempt failed!'
            screenshot = self.api.get_agent_screenshot(self.device.name, self.name)

            self.results.append_error(['screenshot_error',
                                       self.device.name,
                                       self.name,
                                       screenshot])
            logger.debug(' ' * 8 + '%s', error_text)

    def check_local_verification(self):
        "Check local verification and report any errors"

        if not self.backup_failure and self.type == 'agent' and self.backups and self.verification_errors:
            for error in self.verification_errors:
                error_text = 'Local Verification Failure!\n{}\n{}'.format(error['errorType'],error['errorMessage'])
                self.results.append_error(['verification_error', self.device.name, self.name, error['errorType'], error['errorMessage']])
                logger.debug(' ' * 8 + '%s', error_text)

    def check_unprotected_volumes(self):
        "Report any unprotected volumes if arg set to true"

        if self.unprotected_volumes:
            error_text = 'Unprotected Volumes: {0}'.format(escape(','.join(self.unprotected_volumes)))
            self.results.append_error(['informational', self.device.name, self.name, error_text])
            logger.debug(' ' * 8 + '%s', error_text)

    def run_agent_checks(self):
        "Perform agent checks"

        if self.has_local_backups:
            self.check_last_backup_time()
            self.check_last_offsite_time()
            self.check_last_screenshot_time()
            self.check_last_screenshot_status()
            self.check_local_verification()
        
            if self.include_unprotected:
                self.check_unprotected_volumes()
