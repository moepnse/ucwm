#!/opt/python2.7/bin/python
# -*- coding: utf-8 -*-

__author__ = 'Richard Lamboj'
__copyright__ = 'Copyright 2016, Unicom'
__credits__ = ['Richard Lamboj']
__license__ = 'Proprietary'
__version__ = '0.1'
__maintainer__ = 'Richard Lamboj'
__email__ = 'rlamboj@unicom.ws'
__status__ = 'Development'


# standard library imports
import os
import re
import sys
import math
import time
import email
import datetime
import hashlib
import binascii
import imaplib
import ConfigParser
from email.header import decode_header
from email.mime.text import MIMEText
import smtplib

# related third party imports
#import PIL.Image
import cherrypy
from imapclient import IMAPClient

# local application/library specific imports


class UCWM:

    __template_index = u"""
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
    <head>
        <title>UCMS</title>
        <meta name="keywords" content="ucms">
        <meta name="robots" content="index, follow" />
        <meta name="author" content="Richard Lamboj" />
        <!-- HTML 4.x -->
        <meta http-equiv="content-type" content="text/html; charset=utf-8">
        <!-- HTML5 -->
        <meta charset="utf-8">
        <link rel="stylesheet" type="text/css" href="/static/style.css">
    </head>
    <body>
        %(html)s
    </body>
</html>
    """

    __template_login = u"""
        <div id="login">
            <div>
                <form action="%(target)s" method="POST">
                    <h1>Login</h1>
                    <div>
                        <label>Username</label>
                        <input type="text" name="username" class="%(username_class)s" value="">
                    </div>
                    <div>
                        <label>Passwort</label>
                        <input type="password" name="password" class="%(password_class)s" value="">
                    </div>
                    <input type="submit" value="login">
                </form>
            </div>
        </div>
    """

    __template_logged_in = u"""
        %(menu)s <div id="content"><div id="top_menu">%(top_menu)s</div>%(html)s</div>
    """

    __template_menu = u"""
    <div id="menu">
        <img id="logo" src="/static/imgs/unicom_wachslogo.png">
        <a href="/new_mail">New E-Mail</a>
        %(menu_entrys)s
        <a href="/logout/" target="">Logout</a>
    </div>
    """

    __template_message_list = u"""<table>
    <thead>
        <tr><th>Subject</th><th>From</th></tr>
    <thead>
    <tbody>
        %s
    </tbody>
</table>
"""

    __template_message_view = u"""
    <div></div>
    <iframe name="view_port" src="%(url)s"></iframe>
    <div>%(multipart_tree)s</div>
"""

    __template_message = u"""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
    <head>
        <title>UCWM</title>
        <meta name="keywords" content="ucwm">
        <meta name="robots" content="index, follow" />
        <meta name="author" content="Richard Lamboj" />
        <!-- HTML 4.x -->
        <meta http-equiv="content-type" content="text/html; charset=utf-8">
        <!-- HTML5 -->
        <meta charset="utf-8">
    </head>
    <body>
        <pre>
        %s
        </pre>
    </body>
</html>
"""

    __template_new_mail_form = u"""
    <form id="new_mail" method="post" action="">
        <div>
            <label>To</label>
            <input type="text" name="to" value="%(to)s">
        </div>
        <div>
            <label>CC</label>
            <input type="text" name="cc" value="%(cc)s">
        </div>
        <div>
            <label>BCC</label>
            <input type="text" name="bcc" value="%(bcc)s">
        </div>
        <div>
            <label>Subject</label>
            <input type="text" name="subject">
        </div>
        <div>
            <label>Message</label>
            <textarea name="mail">%(mail)s</textarea>
        </div>
        <div class="button_container">
            <input type="submit" value="Send E-Mail">
        </div>
    </form>
"""

    def _build_top_menu(self, params):
        url = '/'
        html = []
        for param in params:
            if param is None:
                continue
            url += param + '/'
            html.append('<a href="%s">%s</a>' % (url, param))
        return u'»'.join(html)

    def __connect_imap(self, username, password):
        #imap = imaplib.IMAP4_SSL(host='purrr.email')
        #imap = imaplib.IMAP4_SSL(host='127.0.0.1')
        imap = IMAPClient('127.0.0.1', use_uid=True, ssl=False)
        print imap.login(username, password)
        return imap

    def _connect_imap(self):
        username = cherrypy.session['username']
        password = cherrypy.session['password']
        return self.__connect_imap(username, password)

    def _build_folder_tree(self, tree):
        html = u'<ul>'
        for index in tree:
            full_path, folder_name, childs = tree[index]
            #html += u'<li><div>%s</div> %s</li>' % (folder, self._build_folder_tree(folder))
            html += u'<li><div><a href="/folder/%(full_path)s">%(folder_name)s</a></div> %(ul)s</li>' % {'folder_name': folder_name, 'full_path': full_path, 'ul': self._build_folder_tree(childs)}
        html += '</ul>'
        return html

    def _get_menu_html(self, folders):
        return self.__template_menu % {"menu_entrys": self._build_folder_tree(folders)}

    def __build_tree(self, tree, delimiter, name):
        folders = name.split(delimiter)
        full_name = None
        for folder in folders:
            if full_name is None:
                full_name = folder
            else:
                full_name = delimiter.join((full_name, folder))
            if not folder in tree:
                new_tree = {}
                tree[folder] = (full_name, folder, new_tree)
                tree = new_tree
            else:
                tree = tree[folder][2]

    def _build_tree(self, folders):
        tree = {}
        for flags, delimiter, name in folders:
            self.__build_tree(tree, delimiter, name)
        return tree

    def _build_message_list(self, folder_name, imap):
        html = u''
        messages = imap.search()
        response = imap.fetch(messages, ['FLAGS', 'ENVELOPE'])
        entrys_html = u''
        for msg_id, data in response.iteritems():
            #print data['ENVELOPE']
            #return ''
            #data['ENVELOPE'].subject.decode()
            value, charset = decode_header(data['ENVELOPE'].subject)[0]
            if charset is None:
                subject = value.decode('ascii', 'replace')
            else:
                subject = value.decode(charset)
            from_ = data['ENVELOPE'].from_[0]
            #mail_from = "%s &lt;%s@%s&gt;" % (from_.name, from_.mailbox, from_.host)
            mail_from = u"""<a href="/new_mail/%s@%s">%s</a>""" % (from_.mailbox, from_.host, from_.name)
            entrys_html = u'<tr><td><a href="/folder/%(folder_name)s/%(msg_id)s">%(subject)s</a></td><td>%(from)s</td></tr>' % {'folder_name': folder_name, 'msg_id': msg_id, 'subject': subject, 'from': mail_from} + entrys_html
        html = html + entrys_html
        html = self.__template_message_list % html
        return html

    @cherrypy.expose
    def new_mail(self, mail_to=None, **kwargs):
        html = u''
        if 'username' in cherrypy.session:
            fields = {
                'subject': '',
                'to': '' if mail_to is None else mail_to,
                'cc': '',
                'bcc': '',
                'mail': ''
            }
            imap = self._connect_imap()
            folders = imap.list_folders()
            tree = self._build_tree(folders)
            if cherrypy.request.method == 'POST':
                msg = MIMEText(kwargs['mail'])
                cc = [] if kwargs['cc'] == '' else kwargs['cc'].split(';')
                bcc = [] if kwargs['bcc'] == '' else kwargs['bcc'].split(';')
                email = cherrypy.session['mail']

                for key in fields:
                    fields[key] = kwargs.get(key, '')

                msg['Subject'] = kwargs['subject']
                msg['From'] = email
                msg['To'] = kwargs['to']
                msg['CC'] = kwargs['cc']
                msg['BCC'] = kwargs['bcc']

                smtp_client = smtplib.SMTP('localhost')
                smtp_client.login(cherrypy.session['username'], cherrypy.session['password'])
                smtp_client.sendmail(email, [kwargs['to']] + cc + bcc, msg.as_string())
                smtp_client.quit()
                html = "Mail has been sent :-)"
            else:
                html = self.__template_new_mail_form % fields
            html = self.__template_logged_in % {
                'top_menu': '',
                'menu':  self._get_menu_html(tree),
                'html': html
            }
            imap.logout()
        return self.__template_index % {'html': html}

    @cherrypy.expose
    def message(self, msg_id):
        html = u''
        if 'username' in cherrypy.session:
            imap = self._connect_imap()
            html = self.__template_logged_in % {
                'top_menu': '',
                'menu':  self._get_menu_html(tree),
                'html': html
            }
        return self.__template_index % {'html': html}

    def _get_message_payload(self, part, *args):
        print part
        part = part.get_payload()[int(args[0])]
        print part
        if len(args) > 1:
            return self._get_message_payload(part, *args[1:])
        else:
            return part

    def _build_multipart_tree(self, part, prefix):
        html = u"<ul>"
        count = 0
        for _part in part.get_payload():
            url = u"%s/%s" % (prefix, count)
            if _part.is_multipart():
                html = html + u"<li>%s</li>" % self._build_multipart_tree(_part, url)
            else:
                html = html + u"""<li><a target="view_port" href="%s">Part</a></li>""" % url
            count =+ 1
        return html + "</ul>"

    def _get_message(self, part):
        charset = part.get_content_charset()
        if charset is None:
            message = part.get_payload(decode=True)
        else:
            message = unicode(part.get_payload(decode=True), str(charset), "ignore")
        return message

    @cherrypy.expose
    def get_message_payload(self, folder_name, msg_id, *args, **kwargs):
        html = u""
        imap = self._connect_imap()
        imap.select_folder(folder_name)
        response = imap.fetch((msg_id,), ('RFC822',))
        if len(response) == 1:
            msg = email.message_from_string(response[int(msg_id)]['RFC822'])
            message = u""
            if msg.is_multipart():
                #messages = msg.get_payload()
                if len(args) > 0:
                    message = self._get_message(self._get_message_payload(msg, *args))
                else:
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get('Content-Disposition'))

                        # skip any text/plain (txt) attachments
                        if content_type in ('text/plain', 'text/html') and 'attachment' not in content_disposition:
                            message = self._get_message(part)
                            break
            else:
                charset = msg.get_content_charset()
                message = self._get_message(msg)
            html = self.__template_message % message
        else:
            pass
        imap.logout()
        return html

    @cherrypy.expose
    def folder(self, folder_name, msg_id=None, **kwargs):
        html = u''
        if 'username' in cherrypy.session:
            imap = self._connect_imap()
            folders = imap.list_folders()
            tree = self._build_tree(folders)
            imap.select_folder(folder_name)
            if msg_id is None:
                html = self._build_message_list(folder_name, imap)
            else:
                response = imap.fetch((msg_id,), ('RFC822',))
                if len(response) == 1:
                    payload_url = '/get_message_payload/%s/%s' % (folder_name, msg_id)
                    msg = email.message_from_string(response[int(msg_id)]['RFC822'])
                    if msg.is_multipart():
                        multipart_tree = self._build_multipart_tree(msg, payload_url)
                    else:
                        multipart_tree = u""
                    html = self.__template_message_view % {'url': payload_url, 'multipart_tree': multipart_tree}
                else:
                    pass
            html = self.__template_logged_in % {
                'top_menu': '',
                'menu':  self._get_menu_html(tree),
                'html': html
            }
            imap.logout()
        return self.__template_index % {'html': html}

    @cherrypy.expose
    def index(self, **kwargs):
        html = u''
        username_class = ''
        password_class = ''
        if cherrypy.request.method == 'POST':
            username = kwargs['username']
            password = kwargs['password']
            imap = self.__connect_imap(username, password)
            cherrypy.session['username'] = username
            cherrypy.session['password'] = password
            cherrypy.session['email'] = "%s@purrr.email" % username
            imap.logout()
            raise cherrypy.HTTPRedirect("/" % kwargs)
        if 'username' in cherrypy.session:
            imap = self._connect_imap()
            folders = imap.list_folders()
            tree = self._build_tree(folders)
            html = self.__template_logged_in % {
                'top_menu': '',
                'menu':  self._get_menu_html(tree),
                'html': html
            }
        else:
            html = self.__template_login % {
                'target': '/',
                'username_class': username_class,
                'password_class': password_class
            }
        return self.__template_index % {'html': html}

    @cherrypy.expose
    def logout(self, **kwargs):
        if 'username' in cherrypy.session:
            del cherrypy.session['username']
        raise cherrypy.HTTPRedirect("/")


if __name__ == '__main__':
    cherrypy.config.update({'server.socket_port': 444,
                        'server.socket_host': '0.0.0.0',
                        'engine.autoreload_on': False,
                        'log.access_file': './access.log',
                        'log.error_file': './error.log'})
    conf = {
        '/': {
            #'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
            'tools.sessions.storage_type': 'file',
            'tools.sessions.storage_path': os.path.join(os.path.abspath(os.getcwd()), 'sessions'),
            'tools.staticdir.root': os.path.abspath(os.getcwd()),
            'tools.encode.on': True,
            'tools.encode.encoding"': "utf-8"
        },
        '/static/imgs': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': './imgs'
        },
        '/static/style.css': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': os.path.join(os.path.abspath(os.getcwd()), 'style.css')
        },
        '/static/script.js': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': os.path.join(os.path.abspath(os.getcwd()), 'script.js')
        },
        '/.well-known': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': './.well-known'
        }
    }
    cherrypy.quickstart(UCWM(), '/', conf)
else:
    cherrypy.tree.mount(UCWM())
    # CherryPy autoreload must be disabled for the flup server to work
    cherrypy.config.update(
        {
            #'server.socket_port': 8080,
            #'server.socket_host': '127.0.0.1',
            'server.socket_file': "/tmp/ucwm",
            'engine.autoreload.on': False,
            'tools.sessions.on': True,
            'tools.sessions.storage_type': 'file',
            'tools.sessions.storage_path': os.path.join(os.path.abspath(os.getcwd()), 'sessions'),
        }
    )
