class DattoAsset():
    '''Class to normalize a Datto Asset 
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
