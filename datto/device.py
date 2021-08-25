# Device
#
# Class for a Datto Device Object
# functions and properties pertaining to a Datto Device

# Import: standard
import logging
from datetime import datetime, timezone
from datto.base import Base

# Import: local
import config

logger = logging.getLogger("Datto Check")


class Device(Base):
    "Datto Device"

    def __init__(self, device, results):
        """Constructor"""
        super()
        self.results = results
        self.name = device['name']
        self.hidden = bool(device['hidden'])
        self.active_tickets = device['activeTickets']
        self.last_seen_date = device['lastSeenDate']
        self.is_offline = False
        self.storage_available = int(device['localStorageAvailable']['size'])
        self.storage_used = int(device['localStorageUsed']['size'])
        self.serial_number = device['serialNumber']

    def is_inactive(self):
        return bool(self.hidden or self.name == 'backupDevice')

    def check_active_tickets(self):
        "Check whether the device has any active tickets open."

        if self.active_tickets:
            error_text = 'Device has {} active {}'.format(\
                self.active_tickets, 'ticket' if self.active_tickets < 2 else 'tickets')
            self.results.append_error(['informational', self.name, 'N/A', error_text])
            logger.debug('    %s', error_text)

    def check_last_checkin(self):
        "Checks the last time the device checked in to the Datto Portal."

        time_string = self.last_seen_date[:22] + self.last_seen_date[23:] # remove the colon from time zone
        device_checkin = datetime.strptime(time_string,
                                           "%Y-%m-%dT%H:%M:%S%z")
        now = datetime.now(timezone.utc) # make 'now' timezone aware
        time_diff = (now - device_checkin).total_seconds()

        if time_diff >= config.CHECKIN_LIMIT:
            error_text = "Last checkin was {} ago.".format(self.display_time(time_diff))
            self.results.append_error(['critical', self.name, 'Appliance Offline', error_text])
            logger.debug('    Appliance Offline')
            self.is_offline = True

    def check_disk_usage(self):
        "Check disk usage reported by the API and calculate percentages"

        total_space = self.storage_available + self.storage_used
        try:
            available_pct = float("{0:.2f}".format(self.storage_used / total_space)) * 100
        except ZeroDivisionError:
            logger.error('    Failure calculating free space (API returned null value')
            return

        if available_pct > config.STORAGE_PCT_THRESHOLD:
            error_text = 'Local storage exceeds {}%.  Current Usage: {}%'.\
                        format(str(config.STORAGE_PCT_THRESHOLD), str(available_pct))
            self.results.append_error(['critical', self.name, 'Low Disk Space', error_text])
            logger.debug('    %s', error_text)

    def run_device_checks(self):
        self.check_active_tickets()
        self.check_last_checkin()
        self.check_disk_usage()
