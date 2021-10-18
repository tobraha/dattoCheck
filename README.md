# Overview

The purpose of this is to automate a daily check of a fleet of Datto Appliances using Datto's REST API. I used to
manually scroll through the Datto portal every day looking for certain errors (backup/screenshot failures, off-site
sync issues, low disk space, etc.). This tool defines error thresholds for things (in config.py) like: time since
last device checkin, time since last successful backup, etc. and queries Datto's API for your device info and sends
an email with the results that looks something like this:

![Screenshot of report output message](https://github.com/tobraha/dattoCheck/blob/master/screenshots/html-report.png)

When building this, I did not have running this on Windows in mind, so I have only tested this on Linux.

# Setup

Python version 3.6 or higher is required to run this.

You'll need a few pieces of information for this script to run properly.

### Datto API Keys

From [Datto Portal Integrations (Admin->Integrations)](https://portal.dattobackup.com/integrations/xml):

* REST API Public Key ("user")
* REST API Secret Key ("password")
* XML API Key

All three of these pieces of information can be found on the "BCDR" Integrations Page.

### Email Info

* Email Username
* Email Password (Optional if you're using something like [Office 365 Direct Send](https://docs.microsoft.com/en-us/exchange/mail-flow-best-practices/how-to-set-up-a-multifunction-device-or-application-to-send-email-using-office-3))
* SMTP Server or "MX Endpoint"
* SMTP port (Default is 25)

_I'm using Office 365 "Direct Send" so that no 365 license or authentication is needed. I'm not familiar
with many other email setups, but this might be problematic with more strict 365 environments (modern
authentication and stuff). You can use something like an app password, but I believe that capability is not
enabled by default._

# Running and Scheduling the Script

There are a couple of ways that you could do this. For my environment, I have cloned this repo to
a Linux system and then use a cron job to run a `git pull` and then run the script. This will automatically
pull any changes I've pushed to the repo here. You could certainly do this to, but if you're being mindful
of security, you may not want to include the `git pull` part.


### Clone the Repo

```bash
sudo git clone https://github.com/tobraha/dattoCheck.git /opt/dattoCheck
cd /opt/dattoCheck
```

### *Optional, but recommended:*

**Create and activate a virtualenv**

```bash
# if necessary, install virtualenv with pip
python3 -m pip install virtualenv

# create a new virtualenv called 'venv'
python3 -m virtualenv venv
source venv/bin/activate
```

### Install Dependencies
```bash
(venv)$ pip install -r requirements.txt
```

### Copy and fill in config.py

```bash
cp config-mk.py config.py
[vim,emacs,nano,whatever] config.py
```

```python
# API authentication
AUTH_USER = '123456a'
AUTH_PASS = '3e47b75000b0924b6c9ba5759a7cf15d'
AUTH_XML  = '437b930db84b8079c2dd804a71936b5f'

# Email configs
EMAIL_FROM  = 'no-reply@example.com'
EMAIL_TO    = ['user1@example.com', 'user2@example.com']
EMAIL_CC    = ['reports@something.com']
EMAIL_LOGIN = EMAIL_FROM # change this if you need to login as a different email than EMAIL_FROM. Only used if EMAIL_PW is set
EMAIL_PW    = ''
EMAIL_MX    = 'mydomain-com.mail.protection.outlook.com'
EMAIL_PORT  = 25
EMAIL_SSL   = True
```

### Adjust any of the alert thresholds to your liking

```python
# Error/Alert threshold settings
CHECKIN_LIMIT = 60 * 20                  # threshold for device offline time; 20 minutes
STORAGE_PCT_THRESHOLD = 95               # threshold for local storage; in percent
LAST_BACKUP_THRESHOLD = 60 * 60 * 12     # threshold for failed backup time; 12 hours
LAST_OFFSITE_THRESHOLD = 60 * 60 * 72    # threshold for last successful off-site; 72 hours
LAST_SCREENSHOT_THRESHOLD = 60 * 60 * 48 # threshold for last screenshot taken; 48 hours
ACTIONABLE_THRESHOLD = 60 * 60 * 24 * 7  # threshold for actionable alerts; 7 days
```

### Running & Testing the Script

I recommend enabling the 'verbose' option if you're running this from the command line. Test it out with:

```bash
python3 main.py -v
```

If you run into any errors, you may need to check the log file which should be at `/var/log/datto_check.log`


If the script cannot write to `/var/log` (or the programs current working directory),
the log file will be in `/tmp`

### Scheduling with cron

While you can run this script manually, it is useful to schedule it to run automatically with cron.
In this example, it will run at 0800 every Monday-Friday.

**Edit your crontab with:**

`crontab -e`

Add something like this to schedule the script:

```bash
0 8 * * 1-5 /usr/bin/python3 /opt/dattoCheck/main.py

# if you setup a virtualenv, use python from your virtualenv instead
0 8 * * 1-5 /opt/dattoCheck/venv/bin/python /opt/dattoCheck/main.py
```

Another optional feature is to use the '-u' option to include any unprotected
volumes in the email report. This can make the report rather lengthy if you have
lots of devices. I like to include this once a week, then just normally the other days:

```bash
# run with '-u' on the first day of the week
0 8 * * 1 /opt/dattoCheck/venv/bin/python /opt/dattoCheck/main.py -u

# then without '-u' Tuesday - Friday:
0 8 * * 2-5 /opt/dattoCheck/venv/bin/python /opt/dattoCheck/main.py

```
# Usage

```
usage: main.py [-h] [-v] [-u]

Using the Datto API, get information on current status of backups, screenshots, local verification, and device issues. To send the results as an email, provide the optional
email parameters.

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         Print verbose output to stdout
  -u, --unprotected-volumes
                        Include any unprotected volumes in the final report

Developed by Tommy Harris, Ryan Shoemaker on September 8, 2019
```
