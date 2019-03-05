# The script is intended to extract TSV data from Ecotaxa


import argparse
import requests
import sys
import datetime
import os
import zipfile
import getpass
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from bs4 import BeautifulSoup
from time import sleep

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

#TO-DO:
# See if SSL verification is needed
# Allow for export with names, path, and export parameters


def loginUser(session, usr):
    url = "https://ecotaxa.obs-vlfr.fr/login"
    csrfpage = session.get(url, verify=False)
    soup = BeautifulSoup(csrfpage.content, 'html5lib')
    csrftoken = soup.find('input', attrs={'name': 'csrf_token'})['value']
    pw = getpass.getpass(prompt='Enter password of ' +usr+"\n:", stream=None)
    print("Attemping log-in...")
    logincred = {'csrf_token': csrftoken,
                 'email': usr,
                 'next': '',
                 "password": pw
                 }
    session.post(url, data=logincred, verify=False)
    cfmloginpage = session.get("https://ecotaxa.obs-vlfr.fr", verify=False)
    soup = BeautifulSoup(cfmloginpage.content, 'html5lib')
    logstat = soup.find('a', attrs={'href':'/logout'})
    if logstat is not None:
        print("Log-in of "+usr+" successful!")
    else:
        sys.exit("Error: Invalid login\n")

    # DEBUG: Display home-screen post login attempt
    # page = session.get("https://ecotaxa.obs-vlfr.fr", verify=False)
    # print(page.content)


def parseID(html):
    html = str(html)
    html = html.split('prj/')[1]
    html = html.split('\"')[0]
    return int(html)

def parseSubtask(html):
    html = str(html)
    html = html.split('Taks ')[1]
    html = html.split(' ')[0]
    return int(html)

def parsePrjName(html):
    html = str(html)
    html = html.split('>')[1]
    html = html.split('<')[0]
    return html

def parseFileName(html):
    html = str(html)
    html = html.split('file ')[1]
    html = html.split('<')[0]
    return html

def recursiveRemove(given, match):
    for num in given:
        if num not in match:
            print("Error: Project id " + str(num) + " not found, continuing without")
            given.remove(num)
            recursiveRemove(given, match)
    return given

def fetchIDs(session, ids=None):
    url = "https://ecotaxa.obs-vlfr.fr/prj/"
    projpage = session.get(url, verify=False)
    soup = BeautifulSoup(projpage.content, 'html5lib')
    projects = soup.find_all('a', attrs={'class': 'btn btn-primary'})
    projids = []
    for i in projects:
        projids.append(parseID(i))
    if ids is None:
        return projids
    else:
        ids = recursiveRemove(ids, projids)
        if len(ids) == 0:
            return None
        else:
            return ids


def fetchFile(session, export):
    url = 'https://ecotaxa.obs-vlfr.fr/Task/Show/' + str(export[1])
    taskpage = session.get(url, verify=False)
    soup = BeautifulSoup(taskpage.content, 'html5lib')
    rawname = soup.find('a', attrs={'href': '/prj/'+str(export[0])})
    folder = parsePrjName(rawname)
    os.mkdir(folder)
    os.chdir(folder)
    rawfile = soup.find('a', attrs={'class': 'btn btn-primary btn-sm'})
    filename = parseFileName(rawfile)
    file = session.get('https://ecotaxa.obs-vlfr.fr/Task/GetFile/'+str(export[1])+'/'+filename)
    with open(filename,'wb') as code:
        code.write(file.content)
    with zipfile.ZipFile(filename, 'r') as zip_ref:
        zip_ref.extractall()
    os.remove(filename)
    print("Download & extraction complete!")


def startTask(session, id):
    url = "https://ecotaxa.obs-vlfr.fr/Task/Create/TaskExportTxt?projid=" + str(id)
    downprops = {
        'exportimagesdoi': '',
        'splitcsvby': '',
        'starttask': 'Y',
        'sumsubtotal': 'W',
        'what': 'TSV'
    }
    infopage = session.post(url, data = downprops, verify = False)
    soup = BeautifulSoup(infopage.content, 'html5lib')
    subtaskraw = soup.find_all('div', attrs={'class':'alert alert-success alert-dismissible'})
    return parseSubtask(subtaskraw)


def downloadProjs(session, explist, path=None):
    done = False
    url = 'https://ecotaxa.obs-vlfr.fr/Task/listall'
    dt = datetime.datetime.now()
    folder = "export_" + dt.strftime("%y%m%d_%H%M%S")

    os.mkdir(folder)
    os.chdir(folder)
    homedir = os.getcwd()
    while not done:
        taskpage = session.get(url, verify=False)
        soup = BeautifulSoup(taskpage.content, 'html5lib')
        for item in explist:
            print('Pinging project '+str(item[0])+ '\'s status')
            rawstatus = soup.find_all('a', attrs={'href': ('/Task/Show/'+str(item[1]))})
            if "Done" in str(rawstatus[1]):
                print("Task "+str(item[1])+' completed, downloading...')
                fetchFile(session, item)
                print("Removing task from Ecotaxa server")
                session.get('https://ecotaxa.obs-vlfr.fr/Task/Clean/'+str(item[1]))
                explist.remove(item)
                os.chdir(homedir)
        if len(explist) == 0:
            return
        else:
            sleep(2)


# Command line arguments
parser = argparse.ArgumentParser()
parser.add_argument(
    '-u', '--user',
    required=True,
    help='<required> email of Ecotaxa account'
                    )
parser.add_argument(
    '-p', '--path',
    required=False,
    help='<optional> path of export'
    )
parser.add_argument(
    '-e', '--export',
    required=False,
    nargs='+',
    type=str,
    help='<INCOMPLETE> export parameters, default is plain TSV'
)
parser.add_argument(
    '-i', '--ids',
    nargs='+',
    type=int,
    help="<required> ids of projects to be downloaded, separated by space(0 for all projects)"
    )


args = parser.parse_args()
user = args.user
ids = args.ids
names = args.ids
path = args.path
options = args.export

with requests.Session() as r:
    loginUser(r, user)
    if path is not None:
        try:
            os.chdir(path)
        except FileNotFoundError:
            print("Error: Provided directory doesn't exist")
            sys.exit()

    if len(ids) == 1 and ids[0] == 0:
        ids = fetchIDs(r)
    else:
        ids = fetchIDs(r, ids)

    if ids is not None:
        # 2D list with structure: [ [id1,task1], [id2,task2], etc]
        exports = []
        for i in ids:
            task = startTask(r,i)
            print("Exporting project " +str(i)+ " as task "+str(task))
            exports.append([i, task])
        downloadProjs(r, exports, path)
        print("Process successfully completed, good-bye!\n")
    else:
        print("Error: No matching project")
