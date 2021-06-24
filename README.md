# Overview
The purpose of this is to automate a daily check of a fleet of Datto Appliances using Datto's REST API. I used to manually scroll through the Datto portal every day looking for certain errors (backup/screenshot failures, off-site sync issues, low disk space, etc.). This tool defines the error thresholds (in config.py) you're trying to find and scrapes the API for your partner account and sends an email with the results that looks something like this:

![Screenshot of report output message](https://github.com/tobraha/dattoCheck/blob/refactor/screenshots/html-report.png)

When building this, I did not have running this on Windows in mind, so I have only tested this on Linux.

# Setup

Python version 3.6 or higher is required to run this.

You'll need a few pieces of information for this script to run properly.

**Datto API Keys**

From [Datto Portal Integrations (Admin->Integrations)](https://portal.dattobackup.com/integrations/xml):

* REST API Public Key ("user")
* REST API Secret Key ("password")
* XML API Key

All three of these pieces of information can be found on the "BCDR" Integrations Page.

**Email Info**

* Email Username
* Email Password (Optional if you're using something like [Office 365 Direct Send](https://docs.microsoft.com/en-us/exchange/mail-flow-best-practices/how-to-set-up-a-multifunction-device-or-application-to-send-email-using-office-3))
* SMTP Server or "MX Endpoint"
* SMTP port [25,587] (Default is 25)

I'm using Office 365 "Direct Send" so that no 365 license or authentication is needed. I'm not familiar with many other email setups, but this might be problematic with more strict 365 environments (modern authentication and stuff). You can use something like an app password, but I believe that capability is not enabled by default.

# Running and Scheduling the Script

**Clone the Repo**

```bash
sudo git clone https://github.com/tobraha/dattoCheck.git /opt/dattoCheck
cd /opt/dattoCheck
```

***-Optional-***

Create and activate a virtualenv:

```bash
python3 -m virtualenv venv
source venv/bin/activate
```

**Install Dependencies**

```bash
pip install -r requirements.txt # might need to use pip3
```

**Running & Testing the Script**

I recommend enabling the 'verbose' option if you're running this from the command line. If you're not sending an email, you'll just need to include the *three* API keys mentioned above:

`python3 main.py -v 123456a 3e47b75000b0924b6c9ba5759a7cf15d 437b930db84b8079c2dd804a71936b5f`

**Scheduling via cron**

This is one of the most useful features for me. This script runs at 0800 every Monday - Friday and sends me the nice email report.

Edit your crontab with:

`crontab -e`

Add something like this to schedule the script:

`0 8 * * 1-5 /usr/bin/git -C /opt/dattoCheck pull ; /usr/bin/python3 /opt/dattoCheck/main.py --send-email --email-to tech-distro-group@mydomain.com --email-from datto-check@mydomain.com --mx-endpoint mydomain-com.mail.protection.outlook.com --starttls 123456a 3e47b75000b0924b6c9ba5759a7cf15d 437b930db84b8079c2dd804a71936b5f`

The '-u' option to include the unprotected volumes can make the report lengthy; I usually add a second cron entry to add the '-u' option on only one day of the week, then exclude it for the rest.

For multiple email recipeints ("To" or "CC"), use the `--email-to` or `--email-cc` args multiple times:

`python3 main.py --send-email --email-to alice@example.com --email-to bob@example.com --email-cc reports@example.com --mx-endpoint example-com.mail.protection.outlook.com --starttls 123456a 3e47b75000b0924b6c9ba5759a7cf15d 437b930db84b8079c2dd804a71936b5f`

```
usage: main.py [-h] [-v] [--send-email] --email-to EMAIL_TO [--email-cc EMAIL_CC] --email-from
               EMAIL_FROM [--email-pw EMAIL_PW] --mx-endpoint MX_ENDPOINT [--smtp-port {25,587}]
               [--starttls]
               AUTH_USER AUTH_PASS XML_API_KEY

Using the Datto API, get information on current status of backups, screenshots, local verification,
and device issues. To send the results as an email, provide the optional email parameters.

positional arguments:
  AUTH_USER             Datto API User (REST API Public Key)
  AUTH_PASS             Datto API Password (REST API Secret Key
  XML_API_KEY           Datto XML API Key

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         Print verbose output to stdout
  --send-email          Set this flag to send an email. Below parameters required if set
  --email-to EMAIL_TO   Email address to send message to. Use more than once for multiple recipients.
  --email-cc EMAIL_CC   (OPTIONAL) Email address to CC. Use more than once for multiple recipients.
  --email-from EMAIL_FROM
                        Email address to send message from
  --email-pw EMAIL_PW   Password to use for authentication
  --mx-endpoint MX_ENDPOINT
                        MX Endpoint of where to send the email
  --smtp-port {25,587}  TCP port to use when sending the email; default=25
  --starttls            Specify whether to use STARTTLS or not
  --unprotected-volumes, -u
                        Include any unprotected volumes in the final report

Developed by Tommy Harris, Ryan Shoemaker on September 8, 2019
```
