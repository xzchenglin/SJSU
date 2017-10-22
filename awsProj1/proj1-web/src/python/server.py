#-*- coding:utf-8 -*-
import json
import shutil,logging
import sys, os, BaseHTTPServer, subprocess, requests, cgi, simplejson

#-------------------------------------------------------------------------------
import urllib2,urllib
import urlparse
import webbrowser
from urllib import FancyURLopener

class ServerException(Exception):
    pass

#-------------------------------------------------------------------------------

class base_case(object):

    def handle_file(self, handler, full_path):
        try:
            with open(full_path, 'rb') as reader:
                content = reader.read()
            handler.send_content(content, 200, full_path)
        except IOError as msg:
            msg = "'{0}' cannot be read: {1}".format(full_path, msg)
            handler.handle_error(msg)

    def index_path(self, handler):
        return os.path.join(handler.full_path, 'index.html')

    def test(self, handler):
        assert False, 'Not implemented.'

    def act(self, handler):
        assert False, 'Not implemented.'

#-------------------------------------------------------------------------------

class case_no_file(base_case):

    def test(self, handler):
        return not os.path.exists(handler.full_path)

    def act(self, handler):
        url = "http://localhost:8001" + handler.path;
        response = requests.get(url, allow_redirects=True);
        handler.send_resp(response);

#-------------------------------------------------------------------------------

class OAuth2(object):
    authorization_url = '/oauth/authorize'
    token_url = '/oauth/token'

    def __init__(self, client_id, client_secret, site, redirect_uri, authorization_url=None, token_url=None):
        """
        Initializes the hook with OAuth2 parameters
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.site = site
        self.redirect_uri = redirect_uri
        if authorization_url is not None:
            self.authorization_url = authorization_url
        if token_url is not None:
            self.token_url = token_url

    def authorize_url(self, scope='', **kwargs):
        """
        Returns the url to redirect the user to for user consent
        """
        oauth_params = {'redirect_uri': self.redirect_uri, 'client_id': self.client_id, 'scope': scope}
        oauth_params.update(kwargs)
        return "%s%s?%s" % (self.site, urllib.quote(self.authorization_url), urllib.urlencode(oauth_params))

    def get_token(self, code, **kwargs):
        """
        Requests an access token
        """
        url = "%s%s" % (self.site, urllib.quote(self.token_url))
        data = {'redirect_uri': self.redirect_uri, 'client_id': self.client_id,
                'client_secret': self.client_secret, 'code': code, 'grant_type': 'authorization_code'}
        data.update(kwargs)
        print url
        print  data
        response = requests.post(url, data=data)

        if isinstance(response.content, basestring):
            try:
                content = json.loads(response.content)
            except ValueError:
                content = urlparse.parse_qs(response.content)
        else:
            content = response.content

        return content

#-------------------------------------------------------------------------------

class case_cgi_file(base_case):

    def run_cgi(self, handler):
        data = subprocess.check_output(["python", handler.full_path])
        handler.send_content(data)

    def test(self, handler):
        return os.path.isfile(handler.full_path) and \
               handler.full_path.endswith('.py')

    def act(self, handler):
        self.run_cgi(handler)

#-------------------------------------------------------------------------------

class case_existing_file(base_case):

    def test(self, handler):
        return os.path.isfile(handler.full_path)

    def act(self, handler):
        self.handle_file(handler, handler.full_path)

#-------------------------------------------------------------------------------

class case_directory_index_file(base_case):

    def test(self, handler):
        return os.path.isdir(handler.full_path) and \
               os.path.isfile(self.index_path(handler))

    def act(self, handler):
        self.handle_file(handler, self.index_path(handler))

#-------------------------------------------------------------------------------

class case_always_fail(base_case):

    def test(self, handler):
        return True

    def act(self, handler):
        raise ServerException("Unknown object '{0}'".format(handler.path))

#-------------------------------------------------------------------------------

class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True

    Cases = [case_no_file(),
             case_cgi_file(),
             case_existing_file(),
             case_directory_index_file(),
             case_always_fail()]

    Error_Page = """\
        <html>
        <body>
        <h1>Error accessing {path}</h1>
        <p>{msg}</p>
        </body>
        </html>
        """

    def check(self, path):
        # code = str(handler.path).split("code=")[1];
        # print code
        # cid = "50mifu4007em89ttcmkles8f7f";
        # cs = "vvsndprvns52dlo8m7310mnvms574vvja0s3v2jq91ja4573gmh";
        # data = 'grant_type=authorization_code&code=' + code + '&client_id=' + cid + '&client_secret=' + cs + "&redirect_uri=https://aliyun.be/";
        # print data
        # url = "https://api.sandbox.amazon.com/auth/o2/token";
        # headers = {'Content-type': 'application/x-www-form-urlencoded', 'Content-Length':len(data)}
        # resp = requests.post(url, data=data, headers=headers)
        # print resp.content
        #TODO
        return True


    def do_GET(self):
        try:
            self.full_path = urllib.unquote(os.getcwd() + self.path)
            print self.full_path

            valid = self.check(self.path);
            if not valid:
                print "!!!redirect"
                login_url = 'https://aliyun.auth.us-east-1.amazoncognito.com/login?redirect_uri=https://aliyun.be/login&client_id=50mifu4007em89ttcmkles8f7f&response_type=code'
                # response = requests.get(login_url, allow_redirects=True)
                # print response
                # handler.send_resp(response)
                webbrowser.open(login_url);

            if "login" in self.path:
                self.path = str(self.path).split("login")[0];
                self.full_path = urllib.unquote(os.getcwd() + self.path);
                print self.path
            for case in self.Cases:
                if case.test(self):
                    case.act(self)
                    break

        except Exception as msg:
            self.handle_error(msg)

    def do_POST(self):
        try:

            if "upload" in self.path:
                ctype, pdict = cgi.parse_header(self.headers.getheader('content-type'))
                fields = cgi.parse_multipart(self.rfile, pdict)
                data = fields.get('file')[0];
                with open("upload/" + self.headers['file-name'], 'wb') as fh:
                    fh.write(data)

            elif "status" in self.path:
                content = self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200)
                self.end_headers()
                json = simplejson.loads(content)
                print (json["detail"]["state"])

            elif "login" in self.path:
                content = self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200)
                self.end_headers()
                print (content)

            self.send_header("content-length", 0)
            self.send_header("content-type", "text")
            self.end_headers();
            self.send_response(200)

            # 处理异常
        except Exception as msg:
            print msg
            self.handle_error(msg)

    def handle_error(self, msg):
        content = self.Error_Page.format(path=self.path, msg=msg)
        self.send_content(content, 404)

    # 发送数据到客户端
    def send_content(self, content, status=200, path=''):
        self.send_response(status)

        if "download" in path:
            print "download:" + path
            self.send_header("Content-Disposition", "attachment; filename=" + path.split("/")[path.split("/").__len__()-1])
            self.send_header("Content-type", "application/force-download")
        else:
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_resp(self, response, status=200):
        self.send_response(status)
        for key, value in response.headers.iteritems():
            self.send_header(key,value);
        self.end_headers()
        self.wfile.write(response.content)

#-------------------------------------------------------------------------------

if __name__ == '__main__':
    serverAddress = ('', 80)
    server = BaseHTTPServer.HTTPServer(serverAddress, RequestHandler)
    server.serve_forever()
