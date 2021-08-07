def email_report(args, body):
    """Email error report to listed recipients.

    args:
        args: arguments from argparse (defined in main.py)
        body: formatted email message body; message only sent as html

    If using Office 365 and only sending to recipients in the
    same domain, it's best to use the "direct send" method because
    authentication is not required. See Option 2 here (you'll need a send connector for this):

    https://docs.microsoft.com/en-us/exchange/mail-flow-best-practices/how-to-set-up-a-multifunction-device-or-application-to-send-email-using-office-3
    """

    logger.info("Preparing and sending email report to: {}".format(args.email_to))
    d = datetime.datetime.today()

    # Email heads
    msg = MIMEMultipart()
    msg['Subject'] = 'Daily Datto Check: {}'.format(d.strftime('%m/%d/%Y'))
    msg['From'] = args.email_from
    msg['To'] = ', '.join(args.email_to)
    if args.email_cc:
        msg['Cc'] = ', '.join( args.email_cc)
    msg.attach(MIMEText(body, 'html'))

    # Send email
    s = smtplib.SMTP(host=args.mx_endpoint, port=int(args.smtp_port))

    try:
        if  args.starttls:
            s.starttls()
        if  args.email_pw:
            s.login(args.email_from, args.email_pw)
        s.send_message(msg)
        s.quit()
        logger.info("Email report sent.")
    except Exception as e:
        logger.critical("Failed to send email message:\n  %s", str(e))


def build_html_email(results_data):
    """Compile all results into HTML tables based on error level."""

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