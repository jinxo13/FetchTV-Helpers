#!/usr/bin/python
import os
import re
import sys
import socket
import requests
from datetime import datetime
import jsonpickle
import xml.etree.ElementTree as ElementTree
from pprint import pprint

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

SAVE_FILE = "fetchtv_save_list.json"
MAX_FILENAME = 255
DISCOVERY_TIMEOUT = 3
REQUEST_TIMEOUT = 2
NO_NUMBER_DEFAULT = ''
FETCHTV_PORT = 49152


class SavedFiles:
    """
    FetchTV recorded items that have already been saved
    Serialised to and from JSON
    """

    @staticmethod
    def load(path):
        """
        Instantiate from JSON file, if it exists
        """
        with open(path + os.path.sep + SAVE_FILE, "a+") as read_file:
            read_file.seek(0)
            content = read_file.read()
            inst = jsonpickle.loads(content) if content else SavedFiles()
            inst.path = path
            return inst

    def __init__(self):
        self.__files = {}
        self.path = ''

    def add_file(self, item):
        self.__files[item.id] = item.title
        # Serialise after each success
        with open(self.path + os.path.sep + SAVE_FILE, "w") as write_file:
            write_file.write(jsonpickle.dumps(self))

    def contains(self, item):
        return item.id in self.__files.keys()


class Location:
    BASE_PATH = "./{urn:schemas-upnp-org:device-1-0}device/{urn:schemas-upnp-org:device-1-0}"

    def __init__(self, url, xml):
        self.url = url
        self.deviceType = get_xml_text(xml, Location.BASE_PATH + "deviceType")
        self.friendlyName = get_xml_text(xml, Location.BASE_PATH + "friendlyName")
        self.manufacturer = get_xml_text(xml, Location.BASE_PATH + "manufacturer")
        self.manufacturerURL = get_xml_text(xml, Location.BASE_PATH + "manufacturerURL")
        self.modelDescription = get_xml_text(xml, Location.BASE_PATH + "modelDescription")
        self.modelName = get_xml_text(xml, Location.BASE_PATH + "modelName")
        self.modelNumber = get_xml_text(xml, Location.BASE_PATH + "modelNumber")


class Folder:
    def __init__(self, xml):
        self.title = xml.find("./{http://purl.org/dc/elements/1.1/}title").text
        self.id = get_xml_attr(xml, 'id', NO_NUMBER_DEFAULT)
        self.parent_id = get_xml_attr(xml, 'parentID', NO_NUMBER_DEFAULT)
        self.items = []

    def add_items(self, items):
        self.items = [itm for itm in items]


class Item:
    MAX_OCTET = 4398046510080

    @property
    def is_recording(self):
        return self.content_length == Item.MAX_OCTET

    def __init__(self, xml):
        self.type = xml.find("./{urn:schemas-upnp-org:metadata-1-0/upnp/}class").text
        self.title = xml.find("./{http://purl.org/dc/elements/1.1/}title").text
        self.id = get_xml_attr(xml, 'id', NO_NUMBER_DEFAULT)
        self.parent_id = get_xml_attr(xml, 'parentID', NO_NUMBER_DEFAULT)
        self.description = xml.find("./{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}description").text
        res = xml.find("./{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}res")
        self.url = res.text
        self.size = int(get_xml_attr(res, 'size', NO_NUMBER_DEFAULT))
        self.duration = ts_to_seconds(get_xml_attr(res, 'duration', '0'))
        self.parent_name = get_xml_attr(res, 'parentTaskName')
        self.content_length = 0

        with requests.get(self.url, stream=True) as r:
            r.raise_for_status()
            if 'CONTENT-LENGTH' in r.headers:
                self.content_length = int(r.headers['CONTENT-LENGTH'])


class Options:
    def __init__(self, argv):
        self.__dict = dict()
        options = ['help', 'ip', 'port', 'recordings', 'info', 'save', 'folder', 'title', 'overwrite']
        for opt in options:
            val = next((arg for arg in argv if arg.startswith('--' + opt)), '')
            if val:
                val = str(val).split('=')
                val = True if len(val) == 1 else val[1]
            self.__dict[opt] = val

        if self.save and self.save.endswith(os.path.sep):
            self.__dict['save'] = self.save.rstrip(os.path.sep)

        if self.folder:
            self.__dict['folder'] = self.folder.replace('"', '')

        if self.title:
            self.__dict['title'] = self.title.replace('"', '')

    @property
    def help(self):
        return self.__dict['help']

    @property
    def info(self):
        return self.__dict['info']

    @property
    def ip(self):
        return self.__dict['ip']

    @property
    def port(self):
        return self.__dict['port']

    @property
    def recordings(self):
        return self.__dict['recordings']

    @property
    def save(self):
        return self.__dict['save']

    @property
    def folder(self):
        return self.__dict['folder']

    @property
    def title(self):
        return self.__dict['title']

    @property
    def overwrite(self):
        return self.__dict['overwrite']


def ts_to_seconds(ts):
    """
    Convert timestamp in the form 00:00:00 to seconds.
    e.g. 00:31:27 = 1887 seconds
    """
    seconds = 0
    for val in ts.split(':'):
        seconds = seconds * 60 + float(val)
    return seconds


def get_xml_attr(xml, name, default=''):
    """
    Return an attribute value if it exists, if not return the default value
    """
    return xml.attrib[name] if name in xml.attrib.keys() else default


def create_valid_filename(filename):
    result = filename.strip()
    # Remove special characters
    for c in '<>:"/\\|?*':
        result = result.replace(c, '')
    # Remove whitespace
    for c in '\t ':
        result = result.replace(c, '_')
    return result[:MAX_FILENAME]


def download_file(url, filename):
    """
    Download the url contents to a file
    """
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(filename + '.lock', 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
        os.rename(filename + '.lock', filename)


def discover_pnp_locations():
    """
    Send a multicast message tell all the pnp services that we are looking
    For them. Keep listening for responses until we hit a 3 second timeout (yes,
    this could technically cause an infinite loop). Parse the URL out of the
    'location' field in the HTTP header and store for later analysis.

    @return the set of advertised upnp locations
    """
    locations = set()
    location_regex = re.compile("location:[ ]*(.+)\r\n", re.IGNORECASE)
    ssdp_discover = ('M-SEARCH * HTTP/1.1\r\n' +
                     'HOST: 239.255.255.250:1900\r\n' +
                     'MAN: "ssdp:discover"\r\n' +
                     'MX: 1\r\n' +
                     'ST: ssdp:all\r\n' +
                     '\r\n')

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(ssdp_discover.encode('ASCII'), ("239.255.255.250", 1900))
    sock.settimeout(DISCOVERY_TIMEOUT)
    try:
        while True:
            data = sock.recvfrom(1024)[0]  # buffer size is 1024 bytes
            location_result = location_regex.search(data.decode('ASCII'))
            if location_result and not (location_result.group(1) in locations):
                locations.add(location_result.group(1))
    except socket.error:
        sock.close()

    return locations


def get_xml_text(xml, xml_name, default=''):
    """
    Return the text value if it exists, if not return the default value
    """
    try:
        return xml.find(xml_name).text
    except AttributeError:
        return default


def parse_locations(locations):
    """
    Loads the XML at each location and prints out the API along with some other
    interesting data.

    @param locations a collection of URLs
    @return igd_ctr (the control address) and igd_service (the service type)
    """
    result = []
    if len(locations) > 0:
        for location in locations:
            try:
                resp = requests.get(location, timeout=REQUEST_TIMEOUT)
                try:
                    xml_root = ElementTree.fromstring(resp.text)
                except:
                    continue

                loc = Location(location, xml_root)
                result.append(loc)

            except requests.exceptions.ConnectionError:
                print('[!] Could not load %s' % location)
            except requests.exceptions.ReadTimeout:
                print('[!] Timeout reading from %s' % location)
    return result


def get_fetch_recordings(location, options: Options):
    """
    Return all FetchTV recordings, or only for a particular folder if specified
    """
    parsed = urlparse(location.url)
    resp = requests.get(location.url, timeout=REQUEST_TIMEOUT)
    try:
        xml_root = ElementTree.fromstring(resp.text)
    except:
        print('\t[!] Failed XML parsing of %s' % location.url)
        return
    cd_ctr = ''
    cd_service = ''

    print('\t-> Services:')
    services = xml_root.findall(".//*{urn:schemas-upnp-org:device-1-0}serviceList/")
    for service in services:
        # Add a lead in '/' if it doesn't exist
        scp = service.find('./{urn:schemas-upnp-org:device-1-0}SCPDURL').text
        if scp[0] != '/':
            scp = '/' + scp
        service_url = parsed.scheme + "://" + parsed.netloc + scp

        # read in the SCP XML
        resp = requests.get(service_url, timeout=REQUEST_TIMEOUT)
        service_xml = ElementTree.fromstring(resp.text)

        actions = service_xml.findall(".//*{urn:schemas-upnp-org:service-1-0}action")
        for action in actions:
            if action.find('./{urn:schemas-upnp-org:service-1-0}name').text == 'Browse':
                print('\t\t=> API: %s' % service_url)
                cd_ctr = parsed.scheme + "://" + parsed.netloc + service.find(
                    './{urn:schemas-upnp-org:device-1-0}controlURL').text
                cd_service = service.find('./{urn:schemas-upnp-org:device-1-0}serviceType').text
                break

    base_folders = find_directories(cd_ctr, cd_service)
    recording = next((folder for folder in base_folders if folder.title == 'Recordings'), False)
    if recording:
        recordings = find_directories(cd_ctr, cd_service, recording.id)
        results = []
        for recording in recordings:
            result = {'title': recording.title, 'items': []}
            # Skip not matching folders
            if options.folder and recording.title.lower().find(options.folder.lower()) == -1:
                continue
            print('\t -- ' + recording.title)
            for item in recording.items:
                # Skip not matching titles
                if options.title and item.title.lower().find(options.title.lower()) == -1:
                    continue
                if item.is_recording:
                    print('\t\t -- (Recording) %s (%s)' % (item.title, item.url))
                else:
                    print('\t\t -- %s (%s)' % (item.title, item.url))
                    result['items'].append(item)
            results.append(result)
        return results
    return False


def find_directories(p_url, p_service, object_id='0'):
    """
    Send a 'Browse' request for the top level directory. We will print out the
    top level containers that we observer. I've limited the count to 10.

    @param p_url the url to send the SOAPAction to
    @param p_service the service in charge of this control URI
    """
    result = []
    payload = ('<?xml version="1.0" encoding="utf-8" standalone="yes"?>' +
               '<s:Envelope s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/" xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">' +
               '<s:Body>' +
               '<u:Browse xmlns:u="' + p_service + '">' +
               '<ObjectID>' + object_id + '</ObjectID>' +
               '<BrowseFlag>BrowseDirectChildren</BrowseFlag>' +
               '<Filter>*</Filter>' +
               '<StartingIndex>0</StartingIndex>' +
               # '<RequestedCount>10</RequestedCount>' +
               '<SortCriteria></SortCriteria>' +
               '</u:Browse>' +
               '</s:Body>' +
               '</s:Envelope>')

    soap_action_header = {'Soapaction': '"' + p_service + '#Browse' + '"',
                        'Content-type': 'text/xml;charset="utf-8"'}

    resp = requests.post(p_url, data=payload, headers=soap_action_header)
    if resp.status_code != 200:
        print('\t\tRequest failed with status: %d' % resp.status_code)
        return

    xml_root = ElementTree.fromstring(resp.text)
    containers = xml_root.find(".//*Result").text
    if not containers:
        return

    xml_root = ElementTree.fromstring(containers)
    containers = xml_root.findall("./{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}container")
    for container in containers:
        if container.find("./{urn:schemas-upnp-org:metadata-1-0/upnp/}class").text.find("object.container") > -1:
            folder = Folder(container)
            result.append(folder)
            folder.add_items(find_items(p_url, p_service, container.attrib['id']))
    return result


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
               # '<RequestedCount>10</RequestedCount>' +
               '<SortCriteria></SortCriteria>' +
               '</u:Browse>' +
               '</s:Body>' +
               '</s:Envelope>')

    soap_action_header = {'Soapaction': '"' + p_service + '#Browse' + '"',
                        'Content-type': 'text/xml;charset="utf-8"'}

    resp = requests.post(p_url, data=payload, headers=soap_action_header)
    if resp.status_code != 200:
        print('\t\tRequest failed with status: %d' % resp.status_code)
        return result

    xml_root = ElementTree.fromstring(resp.text)
    containers = xml_root.find(".//*Result").text
    if not containers:
        return result

    xml_root = ElementTree.fromstring(containers)
    items = xml_root.findall("./{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}item")
    for item in items:
        itm = Item(item)
        result.append(itm)
    return result


def discover_fetch(ip=False, port=FETCHTV_PORT):
    location_urls = discover_pnp_locations() if not ip else ['http://%s:%i/MediaServer.xml' % (ip, port)]
    locations = parse_locations(location_urls)
    # Find fetch
    result = next((location for location in locations if location.manufacturerURL == 'http://www.fetch.com/'), False)
    if not result:
        print('\tERROR: Unable to locate Fetch UPNP service')
        print('[+] Discovery failed')
        return False

    print('[+] Discovery successful: ' + result.url)
    return result


def show_help():
    print('''
      Usage:
        fetchtv_upnp.py <command> <options>
        
        e.g.
        --> Display Fetch Server details
        fetchtv_upnp.py --info
        
        --> Save any new recordings to C:\\Temp
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --save='C:\\temp'

        --> Save any new episodes for the show '2 Broke Girls' to C:\\Temp
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --folder='2 Broke Girls' --save='C:\\temp'
        
        --> Save episode contianing 'S4 E12' for the show '2 Broke Girls' to C:\\Temp
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --overwrite --folder='2 Broke Girls' --title='S4 E12' --save='C:\\temp'

        Commands:
        --help       --> Display this help
        --info       --> Attempts auto-discovery and returns the Fetch Servers details
        --recordings --> List or save recordings

        Options:
        --ip=<ip_address>  --> Specify the IP Address of the Fetch Server, if auto-discovery fails
        --port=<port>      --> Specify yhe port of the Fetch Server, if auto-discovery fails, normally 49152
        --overwrite        --> Will save and overwrite any existing files
        --save=<path>      --> Save recordings to the specified path
        --folder=<text>    --> Only return recordings where the folder contains the specified text
        --title=<text>     --> Only return recordings where the item contains the specified text
    ''')


def save_recordings(recordings, options: Options):
    """
    Save all recordings for the specified folder (if not already saved)
    """
    some_to_record = False
    path = options.save
    saved_files = SavedFiles.load(path)
    for show in recordings:
        for item in show['items']:
            if item.is_recording:
                print('\t -- Skipping currently recording item: [%s - %s]' % (show['title'], item.title))
                continue
            if options.overwrite or not saved_files.contains(item):
                some_to_record = True
                directory = path + os.path.sep + create_valid_filename(show['title'])
                if not os.path.exists(directory):
                    try:
                        os.makedirs(directory)
                    except OSError:
                        pass
                file_path = directory + os.path.sep + create_valid_filename(item.title) + '.mpeg'

                # Check if already writing
                lock_file = file_path + '.lock'
                if os.path.exists(lock_file):
                    print('\t -- Already writing (lock file exists) skipping: [%s]' % item.title)
                    continue

                print('\t -- Writing: [%s] to [%s]' % (item.title, file_path))
                download_file(item.url, file_path)
                saved_files.add_file(item)

    if not some_to_record:
        print('\t -- There is nothing new to record')


def main(argv):
    # TODO replace with argparse.ArgumentParser()
    options = Options(argv)
    if options.help:
        show_help()
        return

    print('[+] Started: %s' % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print('[+] Discover Fetch UPnP location:')
    fetch_server = discover_fetch(ip=options.ip, port=int(options.port) if options.port else FETCHTV_PORT)

    if not fetch_server:
        return

    if options.info:
        pprint(vars(fetch_server))

    if options.recordings:
        print('[+] List Recordings:')
        recordings = get_fetch_recordings(fetch_server, options)

        if options.save:
            print('[+] Saving Recordings:')
            save_recordings(recordings, options)

    print('[+] Done: %s' % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


if __name__ == "__main__":
    main(sys.argv)
