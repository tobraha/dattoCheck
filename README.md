# dattoCheck
Python script that utilizes the Datto API to pull data about device and asset errors.

The purpose of this was to automate a daily check of a fleet of Datto Appliances.  It started out as a text-based CLI application that I would refer to, but the current implementation is setup to be a scheduled task (cron or task scheduler) that runs daily and sends out an email with a list of errors based on parameters set in the global variables.

In order to use it in this way, you need to have the Datto API enabled for your account and you must retrieve the credentials. Furthermore, if sending to an Office 365 account, you must use one of the methods described in their knowledge article:

https://docs.microsoft.com/en-us/exchange/mail-flow-best-practices/how-to-set-up-a-multifunction-device-or-application-to-send-email-using-office-3

In this case, I'm using option 2 (direct send) method so that no authentication is needed. This requires an Exchange connector
in order to function.

For multiple To/CC, use the `--email-to` or `--email-cc` args multiple times:

`python3 Datto_backup_check.py --send-email --email-to alice@example.com --email-to bob@example.com --email-cc reports@example.com --mx-endpoint example-com.mail.protection.outlook.com --starttls 123abc 123456abcdefg 4321dcba`

```
usage: Datto_backup_check.py [-h] [--send-email] --email-to EMAIL_TO
                             [--email-cc EMAIL_CC] --email-from EMAIL_FROM
                             [--email-pw EMAIL_PW] --mx-endpoint MX_ENDPOINT
                             [--smtp-port {25,587}] [--starttls]
                             AUTH_USER AUTH_PASS XML_API_KEY

Using the Datto API, get information on current status of backups,
screenshots, local verification,and device issues. To send the results as an
email, provide the optional email parameters.

positional arguments:
  AUTH_USER             Datto API User (REST API Public Key)
  AUTH_PASS             Datto API Password (REST API Secret Key
  XML_API_KEY           Datto XML API Key

optional arguments:
  -h, --help            show this help message and exit
  --send-email          Set this flag to send an email. Below parameters
                        required if set
  --email-to EMAIL_TO   Email address to send message to. Use more than once
                        for multiple recipients.
  --email-cc EMAIL_CC   (OPTIONAL) Email address to CC. Use more than once for
                        multiple recipients.
  --email-from EMAIL_FROM
                        Email address to send message from
  --email-pw EMAIL_PW   Password to use for authentication
  --mx-endpoint MX_ENDPOINT
                        MX Endpoint of where to send the email
  --smtp-port {25,587}  TCP port to use when sending the email
  --starttls            Specify whether to use STARTTLS or not
  ```
