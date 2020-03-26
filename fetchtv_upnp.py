#!/usr/bin/python
import os
import errno
import re
import sys
import time
import base64
import struct
import socket
import requests
import jsonpickle
import xml.etree.ElementTree as ET
from pprint import pprint

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

class SavedFiles:
    def __init__(self):
        self.__files = {}

    def add_file(self, item):
        self.__files[item.id] = item.title

    def contains(self, item):
        return item.id in self.__files.keys()

class Location:
    BASE_PATH = "./{urn:schemas-upnp-org:device-1-0}device/{urn:schemas-upnp-org:device-1-0}"
    def __init__(self, url, xml):
        self.url = url
        self.deviceType = get_attribute(xml, Location.BASE_PATH + "deviceType")
        self.friendlyName = get_attribute(xml, Location.BASE_PATH + "friendlyName")
        self.manufacturer = get_attribute(xml, Location.BASE_PATH + "manufacturer")
        self.manufacturerURL = get_attribute(xml, Location.BASE_PATH + "manufacturerURL")
        self.modelDescription = get_attribute(xml, Location.BASE_PATH + "modelDescription")
        self.modelName = get_attribute(xml, Location.BASE_PATH + "modelName")
        self.modelNumber = get_attribute(xml, Location.BASE_PATH + "modelNumber")

class Folder:
    def __init__(self, xml):
        self.title = xml.find("./{http://purl.org/dc/elements/1.1/}title").text
        self.id = xml.attrib['id']
        self.items = []

    def add_items(self, items):
        self.items = [itm for itm in items]

class Item:
    def __init__(self, xml):
        self.type = xml.find("./{urn:schemas-upnp-org:metadata-1-0/upnp/}class").text
        self.title = xml.find("./{http://purl.org/dc/elements/1.1/}title").text
        self.id = xml.attrib['id']
        self.description = xml.find("./{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}description").text
        self.url = xml.find("./{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}res").text

class Options:
    def __init__(self, argv):
        self.__dict = dict()
        options = ['help','ip','port','recordings','info','save','folder']
        for opt in options:
            val = next((arg for arg in argv if arg.startswith('--'+opt)), False)
            if val:
                val = val.split('=')
                val = True if len(val) == 1 else val[1]
            self.__dict[opt] = val
        
        if self.save and self.save.endswith(os.path.sep):
            self.__dict['save'] = self.save.rstrip(os.path.sep)

        if self.folder:
            self.__dict['folder'] = self.folder.replace('"','')


    @property
    def help(self): return self.__dict['help']
    @property
    def info(self): return self.__dict['info']
    @property
    def ip(self): return self.__dict['ip']
    @property
    def port(self): return self.__dict['port']
    @property
    def recordings(self): return self.__dict['recordings']
    @property
    def save(self): return self.__dict['save']
    @property
    def folder(self): return self.__dict['folder']

def download_file(url, local_filename):
    # NOTE the stream=True parameter below
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): 
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
                    # f.flush()
    return local_filename

###
# Send a multicast message tell all the pnp services that we are looking
# For them. Keep listening for responses until we hit a 3 second timeout (yes,
# this could technically cause an infinite loop). Parse the URL out of the
# 'location' field in the HTTP header and store for later analysis.
#
# @return the set of advertised upnp locations
###
def discover_pnp_locations():
    locations = set()
    location_regex = re.compile("location:[ ]*(.+)\r\n", re.IGNORECASE)
    ssdpDiscover = ('M-SEARCH * HTTP/1.1\r\n' +
                    'HOST: 239.255.255.250:1900\r\n' +
                    'MAN: "ssdp:discover"\r\n' +
                    'MX: 1\r\n' +
                    'ST: ssdp:all\r\n' +
                    '\r\n')

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(ssdpDiscover.encode('ASCII'), ("239.255.255.250", 1900))
    sock.settimeout(3)
    try:
        while True:
            data = sock.recvfrom(1024)[0] # buffer size is 1024 bytes
            location_result = location_regex.search(data.decode('ASCII'))
            if location_result and (location_result.group(1) in locations) == False:
                locations.add(location_result.group(1))
    except socket.error:
        sock.close()

    return locations

def get_attribute(xml, xml_name, default=''):
    try:
        return xml.find(xml_name).text
    except AttributeError:
        return default

###
# Loads the XML at each location and prints out the API along with some other
# interesting data.
#
# @param locations a collection of URLs
# @return igd_ctr (the control address) and igd_service (the service type)
###
def parse_locations(locations):
    result = []
    if len(locations) > 0:
        for location in locations:
            try:
                resp = requests.get(location, timeout=2)
                try:
                    xmlRoot = ET.fromstring(resp.text)
                except:
                    continue
                
                loc = Location(location, xmlRoot)
                result.append(loc)

            except requests.exceptions.ConnectionError:
                #print('[!] Could not load %s' % location)
                pass
            except requests.exceptions.ReadTimeout:
                #print('[!] Timeout reading from %s' % location)
                pass
    return result

def get_fetch_recordings(location, folder=False):
    try:
        parsed = urlparse(location.url)
        resp = requests.get(location.url, timeout=2)
        try:
            xmlRoot = ET.fromstring(resp.text)
        except:
            print('\t[!] Failed XML parsing of %s' % location.url)
            return
        cd_ctr = ''
        cd_service = ''

        print('\t-> Services:')
        services = xmlRoot.findall(".//*{urn:schemas-upnp-org:device-1-0}serviceList/")
        for service in services:
            # Add a lead in '/' if it doesn't exist
            scp = service.find('./{urn:schemas-upnp-org:device-1-0}SCPDURL').text
            if scp[0] != '/':
                scp = '/' + scp
            serviceURL = parsed.scheme + "://" + parsed.netloc + scp

            # read in the SCP XML
            resp = requests.get(serviceURL, timeout=2)
            try:
                serviceXML = ET.fromstring(resp.text)
            except:
                print('\t\t\t[!] Failed to parse the response XML')
                continue

            actions = serviceXML.findall(".//*{urn:schemas-upnp-org:service-1-0}action")
            for action in actions:
                if action.find('./{urn:schemas-upnp-org:service-1-0}name').text == 'Browse':
                    print('\t\t=> API: %s' % serviceURL)
                    cd_ctr = parsed.scheme + "://" + parsed.netloc + service.find('./{urn:schemas-upnp-org:device-1-0}controlURL').text
                    cd_service = service.find('./{urn:schemas-upnp-org:device-1-0}serviceType').text
                    break

        base_folders = find_directories(cd_ctr, cd_service)
        recording = next((folder for folder in base_folders if folder.title == 'Recordings'), False)
        if recording:
            recordings = find_directories(cd_ctr, cd_service, recording.id)
            for recording in recordings:
                #Skip not matching folders
                if folder and folder.lower() != recording.title.lower():
                    continue
                print('\t -- ' + recording.title)
                for item in recording.items:
                    print('\t\t -- '+item.title+' (%s)' % item.url)
            return recordings
        return False

    except requests.exceptions.ConnectionError:
        print('[!] Could not load %s' % location)
    except requests.exceptions.ReadTimeout:
        print('[!] Timeout reading from %s' % location)

###
# Send a 'Browse' request for the top level directory. We will print out the
# top level containers that we observer. I've limited the count to 10.
#
# @param p_url the url to send the SOAPAction to
# @param p_service the service in charge of this control URI
###
def find_directories(p_url, p_service, object_id='0'):
    result = []
    payload = ('<?xml version="1.0" encoding="utf-8" standalone="yes"?>' +
               '<s:Envelope s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/" xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">' +
               '<s:Body>' +
               '<u:Browse xmlns:u="' + p_service + '">' +
               '<ObjectID>' + object_id + '</ObjectID>' +
               '<BrowseFlag>BrowseDirectChildren</BrowseFlag>' +
               '<Filter>*</Filter>' +
               '<StartingIndex>0</StartingIndex>' +
               '<RequestedCount>10</RequestedCount>' +
               '<SortCriteria></SortCriteria>' +
               '</u:Browse>' +
               '</s:Body>' +
               '</s:Envelope>')

    soapActionHeader = { 'Soapaction' : '"' + p_service + '#Browse' + '"',
                         'Content-type' : 'text/xml;charset="utf-8"' }

    resp = requests.post(p_url, data=payload, headers=soapActionHeader)
    if resp.status_code != 200:
        print('\t\tRequest failed with status: %d' % resp.status_code)
        return

    try:
        xmlRoot = ET.fromstring(resp.text)
        containers = xmlRoot.find(".//*Result").text
        if not containers:
            return

        xmlRoot = ET.fromstring(containers)
        containers = xmlRoot.findall("./{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}container")
        for container in containers:
            if container.find("./{urn:schemas-upnp-org:metadata-1-0/upnp/}class").text.find("object.container") > -1:
                folder = Folder(container)
                result.append(folder)
                folder.add_items(find_items(p_url, p_service, container.attrib['id']))
    except:
        print('\t\t[!] Failed to parse the response XML')
    return result

###
# Send a 'Browse' request for the top level directory. We will print out the
# top level containers that we observer. I've limited the count to 10.
#
# @param p_url the url to send the SOAPAction to
# @param p_service the service in charge of this control URI
###
def find_items(p_url, p_service, object_id):
    result = []
    payload = ('<?xml version="1.0" encoding="utf-8" standalone="yes"?>' +
               '<s:Envelope s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/" xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">' +
               '<s:Body>' +
               '<u:Browse xmlns:u="' + p_service + '">' +
               '<ObjectID>' + object_id + '</ObjectID>' +
               '<BrowseFlag>BrowseDirectChildren</BrowseFlag>' +
               '<Filter>*</Filter>' +
               '<StartingIndex>0</StartingIndex>' +
               '<RequestedCount>10</RequestedCount>' +
               '<SortCriteria></SortCriteria>' +
               '</u:Browse>' +
               '</s:Body>' +
               '</s:Envelope>')

    soapActionHeader = { 'Soapaction' : '"' + p_service + '#Browse' + '"',
                         'Content-type' : 'text/xml;charset="utf-8"' }

    resp = requests.post(p_url, data=payload, headers=soapActionHeader)
    if resp.status_code != 200:
        print('\t\tRequest failed with status: %d' % resp.status_code)
        return

    try:
        xmlRoot = ET.fromstring(resp.text)
        containers = xmlRoot.find(".//*Result").text
        if not containers:
            return result

        xmlRoot = ET.fromstring(containers)
        items = xmlRoot.findall("./{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}item")
        for item in items:
            itm = Item(item)
            result.append(itm)
        return result
    except:
        print('\t\t\t[!] Failed to parse the response XML')

def discover_fetch(ip=False, port=49152):
    location_urls = discover_pnp_locations() if not ip else ['http://%s:%i/MediaServer.xml' % (ip, port)]
    locations = parse_locations(location_urls)
    #Find fetch
    result = next((location for location in locations if location.manufacturerURL == 'http://www.fetch.com/'), False)
    if not result:
        print('\tERROR: Unable to locate Fetch UPNP service')
        print('[+] Discovery failed')
        return False

    print('[+] Discovery successful: '+result.url)
    return result

def show_help():
    print('Usage:')
    print('\t\t fetchtv_upnp.py --help')
    print('\t\t --> Displays this help')
    print('')
    print('\t\t fetchtv_upnp.py --info')
    print('\t\t -->  Attempts auto-discovery and returns the Fetch Servers details')
    print('')
    print('\t\t fetchtv_upnp.py --ip=192.168.1.100 --port=49152')
    print('\t\t --> Returns the Fetch Servers details for the specified ip/port')
    print('')
    print('\t\t fetchtv_upnp.py --recordings')
    print('\t\t -->  Returns the list of all recordings')
    print('')
    print('\t\t fetchtv_upnp.py --recordings --save=<path>')
    print('\t\t -->  Saves recordings to the specified path, if they haven\'t already been copied')
    print('')
    print('\t\t fetchtv_upnp.py --recordings --folder=\'2 Broke Girls\' --save=<path>')
    print('\t\t -->  Saves recordings for the specified folder to the specified path, if they haven\'t already been copied')

def save_recordings(recordings, path, folder):
    saved_files = SavedFiles()
    with open(path + os.path.sep + "save_list.json", "a+") as read_file:
        read_file.seek(0)
        content = read_file.read()
        if content:
            saved_files = jsonpickle.loads(content)
    for show in recordings:
        if folder and folder.lower() != show.title.lower():
            continue

        for item in show.items:
            if not saved_files.contains(item):
                directory = path + os.path.sep + show.title.replace(' ', '_')
                if not os.path.exists(directory):
                    try:
                        os.makedirs(directory)
                    except OSError as exc:
                        if exc.errno != errno.EEXIST:
                            raise
                        pass                        
                file_path = directory + os.path.sep + item.title.replace(' ', '_') + '.mpeg'
                print('\t -- Writing: [%s] to [%s]' % (item.title, file_path))
                download_file(item.url, file_path)
                saved_files.add_file(item)
    
                #Save after each success
                with open(path + os.path.sep + "save_list.json", "w") as write_file:
                    write_file.write(jsonpickle.dumps(saved_files))

###
# Discover upnp services on the LAN and print out information needed to
# investigate them further. Also prints out port mapping information if it
# exists
###
def main(argv):
    options = Options(argv)
    if options.help:
        show_help()
        return

    print('[+] Discover Fetch UPnP location:')
    fetch_server = discover_fetch(ip=options.ip, port=int(options.port) if options.port else 49152)

    if not fetch_server:
        return

    if options.info:
        pprint(vars(fetch_server))

    if options.recordings:
        print('[+] List Recordings:')
        recordings = get_fetch_recordings(fetch_server, options.folder)

    if options.recordings and options.save:
        print('[+] Saving Recordings:')
        save_recordings(recordings, options.save, options.folder)

    print("[+] Done")

if __name__ == "__main__":
    main(sys.argv)
