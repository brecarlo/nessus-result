#!/usr/bin/env python

#    The MIT License (MIT)
#
#    Copyright (c) 2013 Carlo Bressan
#
#    Permission is hereby granted, free of charge, to any person obtaining a copy of
#    this software and associated documentation files (the "Software"), to deal in
#    the Software without restriction, including without limitation the rights to
#    use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
#    the Software, and to permit persons to whom the Software is furnished to do so,
#    subject to the following conditions:
#
#    The above copyright notice and this permission notice shall be included in all
#    copies or substantial portions of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
#    FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
#    COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
#    IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
#    CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
#    ----------------------------------------------------------------
#    Basic usage:
#    - List available results:    nessus-result.py -s SERVER -l
#    - Export results:            nessus-result.py -s SERVER -e
#    - Import results:            nessus-result.py -s SERVER -i -r <file list>
#
#    For more options, see nessus-result.py -h


import sys, os, string, argparse, datetime
import urllib, urllib2, getpass, cookielib, fnmatch
import xml.etree.ElementTree as etree
from poster.encode import multipart_encode

def login(server, username, password):
    cookie = cookielib.CookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie))
    param = urllib.urlencode({'login' : username, 'password' : password})
    try:
        opener.open(server + '/login', param)
    except:
        print("Unable to connect to server")
        sys.exit(1)
    return opener

def listResults(opener, server):
    param = urllib.urlencode({'seq' : '1'})
    resp = opener.open(server + '/report/list', param)
    xmlResp = resp.read()
    resp.close()
    root = etree.fromstring(xmlResp)
    results=[]
    for result in root.findall('.//report'):
        resultId = result.find('name').text
        name = result.find('readableName').text
        timestamp = result.find('timestamp').text
        results.append({'id':resultId, 'name':name, 'timestamp':timestamp})
    return results

def exportResult(opener, server, resultId):
    param = urllib.urlencode({'report' : resultId})
    resp = opener.open(server + '/file/report/download', param)
    return resp.read()

def importResult(opener, server, fileName):
    # Translate tab
    intab = "/\:"
    outtab = "___"
    trantab = string.maketrans(intab, outtab)

    # Translate filename to avoid errors with special characters
    fileNameModified=fileName.translate(trantab)

    # Upload file
    payload_temp, headers = multipart_encode({"Filedata": open(fileName)})
    payload=str().join(payload_temp)
    payload=payload.replace(fileName,fileNameModified,1)
    request = urllib2.Request(server + '/file/upload', payload, headers)
    resp = opener.open(request)
    resp.close()

    # Importing
    param = urllib.urlencode({'file' : fileNameModified, 'seq' : '1'})
    resp = opener.open(server + '/file/report/import', param)
    resp.close()

def main():
    # Options
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--server', type=str, help='Server name or IP', default='')
    parser.add_argument('--port', type=str, help='Port (default 8834)', default='8834')
    parser.add_argument('-u', '--username', type=str, help='Username (if not specified, it will be prompted)', default='')
    parser.add_argument('-p', '--password', type=str, help='Password (if not specified, it will be prompted)', default='')

    parser.add_argument('-l', action='store_true', help='List available results')

    parser.add_argument('-e', action='store_true', help='Export results')
    parser.add_argument('-f', '--filter', type=str, help='Filter for exporting, in Unix filename pattern matching style', default='')
    parser.add_argument('--force', action='store_true', help='Force overwriting existing result')

    parser.add_argument('-i', action='store_true', help='Import results')
    parser.add_argument('-r', '--result', type=str, nargs='+', help='Result file list', default='')

    options = parser.parse_args()

    # Check options
    if (options.server==''):
        print("No server specified (-s)")
        parser.print_help()
        sys.exit(1)
    if (options.l==False and options.e==False and options.i==False):
        print("No action specified (-l | -e | -i)")
        parser.print_help()
        sys.exit(1)

    # Credentials
    username=options.username
    if (username==''):
        username = raw_input('Enter username: ')
    password=options.password
    if (password==''):
        password = getpass.getpass()

    # Login
    server = 'https://' + options.server + ':' + options.port
    opener = login(server,username,password)

    # List results
    if (options.l==True):
        results = listResults(opener, server)
        for result in results:
            print datetime.datetime.fromtimestamp(float(result['timestamp'])).strftime('%Y-%m-%d %H:%M:%S') + ' -- ' + result['name']
        sys.exit(0)

    # Export results
    if (options.e==True):
        results = listResults(opener, server)
        for result in results:
            # Check matching name
            if (options.filter=='' or fnmatch.fnmatch(result['name'],options.filter)):
                # Check exixting file
                if (os.path.exists(result['name'] + '.nessus') and not options.force):
                    print ("File " + result['name'] + '.nessus' + ' already exists ==> skipping (use --force to overwrite)')
                else:
                    print ("Exporting "+ result['name'] + ' ...'),
                    content = exportResult(opener, server, result['id'])
                    f = open(result['name'] + '.nessus', 'w')
                    f.write(content)
                    f.close()
                    print "Done"
        sys.exit(0)

    # Import results
    if (options.i==True):
        # Check option
        if (len(options.result)==0):
            print "You have to specify at least one result file (-r)"
        else:
            for fileName in options.result:
                print ("Importing " + fileName + " ..."),
                importResult(opener, server, fileName)
                print "Done"
        sys.exit(0)

if __name__ == "__main__":
    main()



