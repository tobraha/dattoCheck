# Device
#
# Class for a Datto Device Object
# functions and properties pertaining to a Datto Device

# Import: standard
import logging

# Import: local
import config

logger = logging.getLogger("Datto Check")

class Device():
    "Datto Device"

    def __init__(self):
        pass

    def check_active_tickets(self, device):
        "Check whether the device has any active tickets open."

        if device['activeTickets']:
            error_text = 'Appliance has {} active {}'.format(\
                device['activeTickets'], 'ticket' if device['activeTickets'] < 2 else 'tickets' )
            self.append_error(['informational', device['name'], 'N/A', error_text])
            logger.debug("%s:  %s", device['name'], error_text)

    def check_last_checkin(self, device):
        "Checks the last time the device checked in to the Datto Portal."

        time_string = device['lastSeenDate'][:22] + device['lastSeenDate'][23:] # remove the colon from time zone
        device_checkin = datetime.datetime.strptime(time_string,
                                                    "%Y-%m-%dT%H:%M:%S%z")
        now = datetime.datetime.now(datetime.timezone.utc) # make 'now' timezone aware
        time_diff = now - device_checkin

        if time_diff.total_seconds() >= config.CHECKIN_LIMIT:
            error_text = "Last checkin was {} ago.".format(display_time(time_diff.total_seconds()))
            self.append_error(['critical', device['name'], 'Appliance Offline', error_text])
            logger.debug(f"{device['name']}: Appliance Offline")
            return  # do not proceed if the device is offline; go to next device

    def check_disk_usage(self, device):
        "Check disk usage reported by the API and calculate percentages"

        storage_available = int(device['localStorageAvailable']['size'])
        storage_used = int(device['localStorageUsed']['size'])
        total_space = storage_available + storage_used
        try:
            available_pct = float("{0:.2f}".format(storage_used / total_space)) * 100
        except ZeroDivisionError as e:
            logger.error('"{}" calculating free space (API returned null value) on device: "{}"'.format(str(e),device['name']))
            return

        if available_pct > config.STORAGE_PCT_THRESHOLD:
            error_text = 'Local storage exceeds {}%.  Current Usage: {}%'.\
                        format(str(config.STORAGE_PCT_THRESHOLD), str(available_pct))
            self.append_error(['critical', device['name'], 'Low Disk Space', error_text])
            logger.debug("%s:  %s", device['name'], error_text)
