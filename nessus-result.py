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
#    - Import results:            nessus-result.py -s SERVER -i <file list>
#
#    For more options, see nessus-result.py -h


import sys, os, string, argparse, datetime
import urllib, urllib2, getpass, cookielib, fnmatch, json
from poster.encode import multipart_encode


def login(server, username, password):
    cookie = cookielib.CookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie))
    param = urllib.urlencode({'login' : username, 'password' : password})
    try:
        opener.open(server + '/login', param)
    except:
        print("ERROR: Unable to connect to server.")
        sys.exit(1)
    return opener


def sendCommand(opener, url, param=None):
    try:
        return opener.open(url, param)
    except:
        print("ERROR: Unable to connect to server. Check credentials, please.")
        sys.exit(1)


def listTags(opener, server):
    param = urllib.urlencode({'seq' : '1','json':'1'})
    resp = sendCommand(opener, server + '/tag/list', param)
    data = json.loads(resp.read())
    resp.close()

    results={}

    for result in data['reply']['contents']['tags']:
        tagId = result['id']
        tagName = result['name']
        results[tagId]=tagName

    return results

        
def listResults(opener, server, tags):
    param = urllib.urlencode({'seq' : '1','json':'1'})
    resp = sendCommand(opener, server + '/result/list', param)
    data = json.loads(resp.read())
    resp.close()
    
    results=[]
            
    for result in data['reply']['contents']['result']:
        resultId = result['id']
        name = result['name']
        timestamp = result['timestamp']
        tag = result['tags'][0]      
        # Select only 'completed' scan
        status = result['status']
        if (status=='completed'):
            results.append({'id':resultId, 'name':name, 'timestamp':timestamp, 'folder' : tags[tag]})
  
    return results


def exportResult(opener, server, resultId):
    param = urllib.urlencode({'report' : resultId})
    resp = sendCommand(opener, server + '/file/report/download', param)
    return resp.read()


def moveResult(opener, server, id, folder):
    if folder == "":
        return
    
    # Search for folder name (first occurrence)
    tagList = listTags(opener, server)
    tag = -1
    for tempTag in tagList.keys():
        if tagList[tempTag]==folder:
            tag=tempTag
            break
    
    # Create folder (if not exists)
    if tag == -1:
        print "Creating folder " + folder
        param = urllib.urlencode({'name':folder, 'seq' : '1','json':'1'})
        resp = sendCommand(opener,server + '/tag/create', param)
        data = json.loads(resp.read())
        resp.close()
        tag = data['reply']['contents']['id']

    # Move result
    param = urllib.urlencode({'id':id, 'tags':tag,'seq' : '1','json':'1'})
    resp = sendCommand(opener,server + '/tag/replace', param)
    data = json.loads(resp.read())
    resp.close()
        

def importResult(opener, server, fileName, folder=""):
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
    resp = sendCommand(opener,request)
    resp.close()

    # Importing
    param = urllib.urlencode({'file' : fileNameModified, 'seq' : '1', 'json':'1'})
    resp = sendCommand(opener,server + '/result/import', param)
    data = json.loads(resp.read())
    resp.close()
    
    id =  data['reply']['contents']['result']['id']
    
    if folder!="":
        moveResult(opener, server, id, folder)
    

def main():
    # Options
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--server', type=str, help='Server name or IP', default='')
    parser.add_argument('--port', type=str, help='Port (default 8834)', default='8834')
    parser.add_argument('-u', '--username', type=str, help='Username (if not specified, it will be prompted)', default='')
    parser.add_argument('-p', '--password', type=str, help='Password (if not specified, it will be prompted)', default='')

    parser.add_argument('-l', action='store_true', help='List available results (eventually filtered, see filter options)')
    
    parser.add_argument('-e', action='store_true', help='Export results (eventually filtered, see filter options)')
    parser.add_argument('-n', '--name',   type=str, help='Filter for report name, in Unix filename pattern matching style (Ex: nessus-result -l -n "mytest*")', default='')
    parser.add_argument('-f', '--folder', type=str, help='Export/List: Filter for report folder, in Unix filename pattern matching style (Ex: nessus-result -l -f "myfolder*") - Import: save result into the folder (create it if doesn\'t exists)', default='')
    parser.add_argument('--force', action='store_true', help='Export: force overwriting existing file')
    parser.add_argument('--skipdir', action='store_true', help='Export: Skip creation of directory')
    
    parser.add_argument('-i', '--import', dest = 'i', metavar='file', type=str, nargs='+', help='Import result/s', default=None)
    
    parser.add_argument('-V', '--version', action='version', help='Print version and exit', version='Nessus-result version 0.2')

    options = parser.parse_args()

    # Check options
    if (options.server==''):
        print("No server specified (-s)")
        parser.print_help()
        sys.exit(1)
    if (options.l==False and options.e==False and options.i==None):
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
        tags = listTags(opener, server)
        results = listResults(opener, server, tags)
        for result in results:
            # Check matching folder
            if (options.folder=='' or fnmatch.fnmatch(result['folder'],options.folder)):
                # Check matching name
                if (options.name=='' or fnmatch.fnmatch(result['name'],options.name)):
                    print datetime.datetime.fromtimestamp(float(result['timestamp'])).strftime('%Y-%m-%d %H:%M:%S') + ' -- ' + result['folder'] + ' -- ' + result['name'] 
        sys.exit(0)

    # Export results
    if (options.e==True):
        tags = listTags(opener, server)
        results = listResults(opener, server, tags)
        for result in results:
            
            # Check matching folder
            if (options.folder=='' or fnmatch.fnmatch(result['folder'],options.folder)):
                # Check matching name
                if (options.name=='' or fnmatch.fnmatch(result['name'],options.name)):
                    
                    # Create directory
                    folder = result['folder']
                    if (options.skipdir): 
                        filename =result['name'] + '.nessus'
                    else:
                        filename =folder + '/' + result['name'] + '.nessus'
                        if not os.path.exists(folder):
                            os.makedirs(folder)
                        
                    # Check existing file
                    if (os.path.exists(filename) and not options.force):
                        print ("File " + filename + ' (timestamp: ' + datetime.datetime.fromtimestamp(float(result['timestamp'])).strftime('%Y-%m-%d %H:%M:%S') + ') already exists ==> skipping (use --force to overwrite)')
                    else:
                        print ("Exporting "+ result['name'] + ' ...'),
                        content = exportResult(opener, server, result['id'])
                        f = open(filename, 'w')
                        f.write(content)
                        f.close()
                        print "Done"
        sys.exit(0)

    # Import results
    if (options.i != None):
        # Check option
        if (len(options.i)==0):
            print "You have to specify at least one result file (-i)"
        else:
            for fileName in options.i:
                print ("Importing " + fileName + " ...\n"),
                importResult(opener, server, fileName, options.folder)
                print "Done"
        sys.exit(0)

if __name__ == "__main__":
    main()
