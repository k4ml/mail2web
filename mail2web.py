#!/usr/bin/env python

# Copyright (c) 2013, Kamal Bin Mustafa <kamal.mustafa@gmail.com>
#
# Permission to use, copy, modify, and/or distribute this software
# for any purpose with or without fee is hereby granted, provided 
# that the above copyright notice and this permission notice appear
# in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM 
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
# OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
# OF THIS SOFTWARE.

import os
import sys
import email
import smtplib
import datetime
import logging
import traceback
import ConfigParser

import urllib
import urllib2

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import timedelta

HERE = os.path.abspath(os.path.dirname(__file__))

log_file = os.path.join(HERE, 'log.txt')
logging.basicConfig(filename=log_file, level=logging.DEBUG)
logging.info('Start')

config = ConfigParser.ConfigParser()
config.read(os.path.join(HERE, 'config.ini'))

from_addr = config.get('general', 'from_address')
smtp_host = config.get('smtp', 'host') or 'localhost'
smtp_username = config.get('smtp', 'username') or None
smtp_password = config.get('smtp', 'password') or None
smtp_port = config.getint('smtp', 'port') or 25

def send_email(msg, to):
    logging.info('Send start ...')

    s = smtplib.SMTP_SSL(smtp_host, smtp_port)
    s.set_debuglevel(True)
    s.login(smtp_username, smtp_password)

    logging.info('Sending to ')
    to_addr = to
    s.sendmail(from_addr, to_addr, msg.as_string())

    logging.info('Sending done')

def send_error(e, exc_info):
    exc_class, exc, tb = exc_info
    msg = MIMEText("Error: %s %s" % (str(exc_info), traceback.format_tb(tb)))
    msg['Subject'] = 'Error parsing email'
    msg['To'] = from_addr
    send_email(msg, msg['To'])

def get_data(msg):
    data = {}
    data['msg_id'] = msg.get('Message-ID')
    data['sender'] = msg.get('From')
    data['subject'] = msg.get('Subject', '')
    data['to'] = msg.get('To')

    payloads = msg.get_payload()
    content_type = None

    for payload in payloads:
        try:
            content_type = payload.get_content_type()
        except AttributeError as e:
            data['body'] = payloads
            break

        if content_type and content_type == 'text/plain':
            data['body'] = payload.get_payload()
            break
    else:
        data['body'] = ''

    data['body'] = data['body'].strip()
    return data

def receive_email(file_obj=sys.stdin):
    logging.info('Received email')
    subject = ''
    body = ''
    q = ''
    try:
        msg = email.message_from_string(file_obj.read())
    except Exception as e:
        logging.info(str(e))
        exc_info = sys.exc_info()
        return send_error(e, exc_info)

    try:
        data = get_data(msg)
    except Exception as e:
        logging.info(str(e))
        exc_info = sys.exc_info()
        return send_error(e, exc_info)

    if data['body'] != '':
        q = data['body'].strip()
    elif data['subject'] != '':
        q = data['subject'].strip()
    else:
        return

    base_url = 'http://www.duckduckgo.com/html/'
    params = {'q': q}
    logging.info("Params: %s" % params)
    query_string = urllib.urlencode(params)
    resp = urllib2.urlopen(base_url + '?' + query_string)
    content = resp.read()

    msg = MIMEMultipart('alternative')
    msg['Subject'] = "RE: %s" % q[0:80]
    msg['From'] = from_addr
    msg['To'] = data['sender']
    msg['In-Reply-To'] = data['msg_id']
    msg['References'] = data['msg_id']

    # Record the MIME types of both parts - text/plain and text/html.
    part1 = MIMEText('You must enable HTML', 'plain')
    part2 = MIMEText(content, 'html')

    # Attach parts into message container.
    # According to RFC 2046, the last part of a multipart message, in this case
    # the HTML message, is best and preferred.
    msg.attach(part1)
    msg.attach(part2)
    send_email(msg, data['sender'])
    logging.info('DONE')

if __name__ == '__main__':
    try:
        receive_email()
    except Exception as e:
        logging.info(str(e))
        exc_info = sys.exc_info()
        send_error(e, exc_info)
