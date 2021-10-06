# Import: standard

import logging
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Import: local
import config

logger = logging.getLogger("Datto Check")


class Email():

    def __init__(self):
        self.mx_endpoint = config.EMAIL_MX
        self.port = config.EMAIL_PORT
        self.starttls = config.EMAIL_SSL
        self.user = config.EMAIL_LOGIN
        self.password = config.EMAIL_PW

    def send_email(self, email_to, email_from, subject, body, email_cc=None):

        try:
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = email_from
            msg['To'] = ', '.join(email_to)
            if email_cc:
                msg['Cc'] = ', '.join(email_cc)
        except TypeError:
            logger.fatal('[!] Unable to add email recipients. Ensure to/from are iterable types')
            sys.exit(-1)

        msg.attach(MIMEText(body, 'html'))

        # Send email
        s = smtplib.SMTP(host=self.mx_endpoint, port=int(self.port))

        try:
            if  self.starttls:
                s.starttls()
            if  self.password:
                s.login(self.user, self.password)
            s.send_message(msg)
            s.quit()
            logger.info("Email report sent.")
        except Exception as e:
            logger.fatal("Failed to send email message:\n  %s", str(e))
            sys.exit(-1)

    def build_html_report(self, results_data):
        "Compile our Datto Check results into an HTML report for emailing"

        logger.info("Building datto check html report")

        report = '''<html>
    <head>
        <style>
            table,th,td {border: 1px solid black;border-collapse: collapse;text-align: left;}
            th {text-align: center;}
        </style>
    </head>
    <body>'''

        for category in results_data:
            category_name = category
            category = results_data[category]
            if category['errors']:
                report += f"<h1>{category['name']}</h1>"
                report += self.build_report_table(category, category_name)
        report += '</body></html>'
        return report.replace('\n', '')

    def build_report_table(self, category, category_name):
        "Builds and returns an html table with results data"

        colors = ['red', 'yellow']
        table = "<table><tr>"

        # Table headers
        for column in category['columns']:
            table += f"<th>{column}</th>"
        table += "</tr>"

        # Table body
        for error in category['errors']:

            # row color is always the last item if set
            if error[-1] in colors:
                table += '<tr style="background-color: {0};">'.format(error[-1])
            else:
                table += '<tr>'

            for col in range(1, len(category['columns']) + 1):

                if category_name == 'screenshot_error' and col == 3 and 'http' in error[-1]:
                    table += f'<td width="160">{error[col]}</td>'
                else:
                    table += f"<td>{error[col]}</td>"
            table += '</tr>'
        table += '</table>'

        return table
