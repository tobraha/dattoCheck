# Agent
#
# Class for a Datto Agent Object
# functions and properties pertaining to a Datto Agent

# Import: standard
import logging
import datetime

# Import: local
import config
from datto.base import Base

logger = logging.getLogger("Datto Check")

class Agent(Base):
    "Datto Agent"

    def __init__(self, agent):
        "Constructor"
        super()
        self.backup_failure = False
        self.agent = Asset(agent)

    def is_inactive(self):
        """Check agent paused and archive status to determine
        whether or not the agent is active."""
        if self.agent.is_archived or self.agent.is_paused:
            return True
        else:
            return False

    def agent_checks(self, agent, device):
        "Perform agent checks"

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
                        last_snapshot_time = str(self.display_time(time_diff.total_seconds())) + ' ago'
                    else:
                        last_snapshot_time = "(no local snapshots exist)"
                    error_text = '-- "{}": Last scheduled backup failed; last \
                    backup was: {}. Error: "{}"'.format(agent.name,
                                                        last_snapshot_time,
                                                        backup_error)

                    BACKUP_FAILURE = True

                    error_data = ['backup_error',
                                  device['name'],
                                  agent.name,
                                  '{}'.format(last_snapshot_time),
                                  backup_error]

                    if time_diff.total_seconds() > config.ACTIONABLE_THRESHOLD and agent.last_snapshot:
                        self.append_error(error_data, color='red')
                    else:
                        self.append_error(error_data)
                    logger.debug(error_text)

            except IndexError:
                error_text = 'Agent does not seem to have any backups'
                logger.debug("Agent %s does not seem to have any backups.", agent.name)
                self.append_error(['informational', device['name'], agent.name, error_text])

        # Check if latest off-site point exceeds LAST_OFFSITE_THRESHOLD
        if not agent.latest_offsite:
            error_text = 'No off-site backup points exist'
            self.append_error(['informational', device['name'], agent.name, error_text])
            logger.debug("%s - %s", agent.name, error_text)
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
                logger.debug("%s - %s", agent.name, error_text)

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
                logger.debug("%s - %s", agent.name, error_text)

        # check status of last screenshot attempt
        if not BACKUP_FAILURE and agent.type == 'agent' and not agent.last_screenshot_attempt_status:
            error_text = 'Last screenshot attempt failed!'
            screenshot_uri, screenshot_error_message = self.datto.get_agent_screenshot(device['name'],
                                                                                       agent.name)
            if screenshot_uri == -1: screenshot_uri,screenshot_error_message = "",""
            self.append_error(['screenshot_error', device['name'], agent.name,
                              screenshot_uri, escape(screenshot_error_message)])
            logger.debug("%s - %s", agent.name, error_text)

        # check local verification and report any errors
        try:
            if not BACKUP_FAILURE and agent.type == 'agent' and agent.backups and agent.backups[0]['localVerification']['errors']:
                for error in agent.backups[0]['localVerification']['errors']:
                    error_text = 'Local Verification Failure!\n{}\n{}'.format(error['errorType'],error['errorMessage'])
                    self.append_error(['verification_error', device['name'], agent.name, error['errorType'], error['errorMessage']])
                    logger.debug("%s - %s", agent.name, error_text)
        except Exception as e:
            logger.error('Device: "{}" Agent: "{}". {}'.format(device['name'], agent.name, str(e)))

        # report any unprotected volumes if arg set to true
        if self.args.unprotected_volumes:
            if agent.unprotected_volumes:
                error_text = 'Unprotected Volumes: {0}'.format(escape(','.join(agent.unprotected_volumes)))
                self.append_error(['informational', device['name'], agent.name, error_text])
                logger.debug("%s - %s", agent.name, error_text)

class Asset():
    '''Class to initialize & normalize a Datto Asset 
    as an object'''
    def __init__(self, agent):
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
        self.last_screenshot_attempt_status = agent['lastScreenshotAttemptStatus']
        self.last_screenshot_url = agent['lastScreenshotUrl']
        self.fqdn = agent['fqdn']
        self.backups = agent['backups']
        self.type = agent['type']