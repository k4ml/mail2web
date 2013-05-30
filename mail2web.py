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
from email.utils import parseaddr
from datetime import timedelta

HERE = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(HERE, 'vendor'))

import requests

log_file = os.path.join(HERE, 'log.txt')
logging.basicConfig(filename=log_file, level=logging.DEBUG,
                    format='%(asctime)s %(message)s')
logging.info('Start')

config = ConfigParser.ConfigParser()
config.read(os.path.join(HERE, 'config.ini'))

from_addr = config.get('general', 'from_address')
admin_addr = config.get('general', 'admin_address')
debug_addr = config.get('general', 'debug_address')
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
    msg['To'] = admin_addr
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
    email_text = file_obj.read()
    try:
        msg = email.message_from_string(email_text)
        logging.info("Read email")
    except Exception as e:
        logging.info(str(e))
        exc_info = sys.exc_info()
        return send_error(e, exc_info)

    try:
        data = get_data(msg)
        logging.info("Parsed email")
    except Exception as e:
        logging.info(str(e))
        exc_info = sys.exc_info()
        return send_error(e, exc_info)

    if parseaddr(data['to'])[1] == debug_addr:
        try:
            open(os.path.join(HERE, 'data/incoming.txt'), 'w').write(email_text)
            logging.info("Debug email, save to data/incoming.txt")
        except Exception as e:
            logging.info("Failed saving incoming: %s" % str(e))

        return

    logging.info(data)
    if data['body'] != '':
        q = data['body'].strip()
    elif data['subject'] != '':
        q = data['subject'].strip()
    else:
        logging.info("No data")
        return

    base_url = 'https://duckduckgo.com/html/'
    query_string = ''
    headers = {'User-Agent': 'Python urllib2'}

    if q.startswith(('http://', 'https://')):
        resp = requests.get(q, headers=headers)
    else:
        params = {'q': q}
        resp = requests.get(base_url, params=params, headers=headers)
        logging.info("Params: %s" % params)

    logging.info("Done query")
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "RE: %s" % q[0:80]
    msg['From'] = from_addr
    msg['To'] = data['sender']
    msg['In-Reply-To'] = data['msg_id']
    msg['References'] = data['msg_id']

    # Record the MIME types of both parts - text/plain and text/html.
    part1 = MIMEText('You must enable HTML', 'plain')
    part2 = MIMEText(resp.content, 'html')

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
