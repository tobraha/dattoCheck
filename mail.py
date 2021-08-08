import logging
import smtplib
import config
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("Datto Check")

class Email():

    def __init__(self):
        self.mx_endpoint = config.EMAIL_MX
        self.port = config.EMAIL_PORT
        self.starttls = config.EMAIL_SSL
        self.user = config.EMAIL_LOGIN
        self.password = config.EMAIL_PW

    def send_email(self, email_to, email_from, subject, body, email_cc=None):

        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = email_from
        msg['To'] = ', '.join(email_to)
        if config.EMAIL_CC:
            msg['Cc'] = ', '.join(email_cc)
        msg.attach(MIMEText(body, 'html'))

        # Send email
        s = smtplib.SMTP(host=self.mx_endpoint, port=int(self.port))

        try:
            if  self.starttls:
                s.starttls()
            if  config.EMAIL_PW:
                s.login(self.user, self.password)
            s.send_message(msg)
            s.quit()
            logger.info("Email report sent.")
        except Exception as e:
            logger.critical("Failed to send email message:\n  %s", str(e))

    def build_html_report(self, results_data):
        "Compile our Datto Check results into an HTML report for emailing"

        logger.info("Building datto check html report")

        report = '''<html>
    <head>
        <style>
            table,td {
                border: 1px solid black;
                border-collapse: collapse; 
                text-align: left;}
            th {
                text-align: center;}
        </style>
    </head>
    <body>'''

        for category in results_data:
            if category['errors']:
                report += f"<h1>{category['name']}</h1>"
                report += self.build_report_table(category)

    def build_report_table(self, category):
        "Builds and returns an html table with results data"

        colors = ['red', 'yellow']
        table = "<table><tr>"

        for column in category['columns']:
            table += f"<th>{column}</th>"
        table += "</tr>"

        for error in category['errors']:

            # row color is always the last item if set
            if error[-1] in colors:
                table += '<tr style="background-color: {0};">'.format(error[-1])
            else:
                table += '<tr>'
            
            for col in range(len(category['columns'])):
                table += f"<td>{error[col]}</td>"

        return table


    def build_html_stuff(self, results_data):
        "Compile all results into HTML tables based on error level"

        logger.info('Building HTML email message.')
        # create initial html structure
        msg_body = '<html><head><style>table,th,td{border:1px solid black;border-collapse: collapse; text-align: left;}th{text-align:center;}</style></head><body>'

        if results_data['critical']:
            msg_body += '<h1>CRITICAL ERRORS</h1><table>'
            msg_body += '<tr><th>Appliance</th><th>Error Type</th><th>Error Details</th></tr>'
            for error in results_data['critical']:
                msg_body += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td></tr>'
            msg_body += '</table>'

        if results_data['backup_error']:
            msg_body += '<h1>Backup Errors</h1><table>\
            <tr><th>Appliance</th><th>Agent/Share</th><th>Last Backup</th><th>Error Details</th></tr>'
            for error in results_data['backup_error']:
                if len(error) == 5:
                    msg_body += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td><td>' + error[4] + '</td></tr>'
                else:
                    msg_body += '<tr style="background-color: {0};"><td>'.format(error[5]) + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td><td>' + error[4] + '</td></tr>'
            msg_body += '</table>'

        if results_data['offsite_error']:
            msg_body += '<h1>Off-Site Sync Issues</h1><table>\
            <tr><th>Appliance</th><th>Agent/Share</th><th>Error Details</th></tr>'
            for error in results_data['offsite_error']:
                if len(error) == 4:
                    msg_body += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td></tr>'
                else:
                    msg_body += '<tr style="background-color: {0};"><td>'.format(error[4]) + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td></tr>'
            msg_body += '</table>'

        if results_data['screenshot_error']:
            msg_body += '<h1>Screenshot Failures</h1><table>\
            <tr><th>Appliance</th><th>Agent</th><th>Screenshot</th></tr>'
            for error in results_data['screenshot_error']:
                if not error[3]:
                    col_three = 'No Data'
                elif error[3].startswith('http'):
                    col_three = '<a href="{0}"><img src="{0}" alt="" width="160" title="{1}"></img></a>'.format(error[3], error[4])
                else:
                    col_three = error[3]
                if len(error) == 5:
                    msg_body += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td width="160">' + col_three + '</td></tr>'
                else:
                    msg_body += '<tr style="background-color: {0};"><td>'.format(error[5]) + error[1] + '</td><td>' + error[2] + '</td><td width="160">' + col_three + '</td></tr>'
            msg_body += '</table>'

        if results_data['verification_error']:
            msg_body += '<h1>Local Verification Issues</h1><table>\
            <tr><th>Appliance</th><th>Agent</th><th>Error Type</th><th>Error Message</th></tr>'
            for error in results_data['verification_error']:
                if error[4]:
                    error_message = error[4]
                else:
                    error_message = '<none>'
                msg_body += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td><td>' + error_message + '</td></tr>'
            msg_body += '</table>'

        if results_data['informational']:
            msg_body += '<h1>Informational</h1><table>\
            <tr><th>Appliance</th><th>Agent/Share</th><th>Details</th></tr>'
            for error in results_data['informational']:
                msg_body += '<tr><td>' + error[1] + '</td><td>' + error[2] + '</td><td>' + error[3] + '</td></tr>'
            msg_body += '</table>'

        msg_body += '</body></html>'
        return msg_body