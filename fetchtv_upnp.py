#!/usr/bin/python
import os
import sys
import requests
from datetime import datetime
import jsonpickle
from pprint import pprint
from clint.textui import progress
import helpers.upnp as upnp

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

SAVE_FILE = "fetchtv_save_list.json"
FETCHTV_PORT = 49152
CONST_LOCK = '.lock'
MAX_FILENAME = 255
REQUEST_TIMEOUT = 5
MAX_OCTET = 4398046510080

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


class Options:
    PARAM_COMMANDS = ['help', 'info', 'shows', 'recordings']
    PARAM_OPTIONS = ['ip', 'port', 'save', 'folder', 'title', 'overwrite', 'exclude']
    PARAM_MULTI_VALUE = ['title', 'folder', 'exclude']

    def __init__(self, argv):
        self.__dict = dict()
        self.has_command = False
        self.set_commands(argv)
        self.set_options(argv)

        if self.save:
            self.__dict['save'] = self.save.rstrip(os.path.sep)

    def set_commands(self, argv):
        """
        Set commands, only the first one found applies
        """
        for opt in self.PARAM_COMMANDS:
            val = next((arg for arg in argv if arg.startswith('--' + opt)), '')
            self.__dict[opt] = True if val and not self.has_command else False
            if not self.has_command and val:
                self.has_command = True

    def set_options(self, argv):
        # Set option values
        for opt in self.PARAM_OPTIONS:
            val = next((arg for arg in argv if arg.startswith('--' + opt)), '')
            if not val:
                self.__dict[opt] = False
                continue
            val = str(val).split('=')

            if len(val) == 1:  # No value provided
                val = True
            else:
                val = val[1].strip('"\'')  # Trim any quotes

            # Split any multiple values options
            if type(val) is str and opt in self.PARAM_MULTI_VALUE:
                self.__dict[opt] = [item.strip() for item in val.split(',')]
            else:
                self.__dict[opt] = val

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
    def shows(self):
        return self.__dict['shows']

    @property
    def title(self):
        return self.__dict['title']

    @property
    def overwrite(self):
        return self.__dict['overwrite']

    @property
    def exclude(self):
        return self.__dict['exclude']


def create_valid_filename(filename):
    result = filename.strip()
    # Remove special characters
    for c in '<>:"/\\|?*':
        result = result.replace(c, '')
    # Remove whitespace
    for c in '\t ':
        result = result.replace(c, '_')
    return result[:MAX_FILENAME]


def download_file(item, filename):
    """
    Download the url contents to a file
    """
    print('\t -- Writing: [%s] to [%s]' % (item.title, filename))
    with requests.get(item.url, stream=True) as r:
        r.raise_for_status()
        total_length = int(r.headers.get('content-length'))
        if total_length == MAX_OCTET:
            print('\t\t -- [!] Skipping item it\'s currently recording')
            return False

        try:
            with open(filename + CONST_LOCK, 'xb') as f:
                for chunk in progress.bar(r.iter_content(chunk_size=8192), expected_size=(total_length / 8192) + 1):
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)

        except FileExistsError:
            print('\t\t -- [!] Already writing (lock file exists) skipping')
            return False

        except IOError as err:
            print('\t\t -- [!] Error writing file: %s' % err.msg)
            return False

        if os.path.exists(filename):
            os.remove(filename)
        os.rename(filename + CONST_LOCK, filename)
        return True


def get_fetch_recordings(location, options: Options):
    """
    Return all FetchTV recordings, or only for a particular folder if specified
    """
    cd_ctr, cd_service = upnp.get_services(location)
    base_folders = upnp.find_directories(cd_ctr, cd_service)
    recording = [folder for folder in base_folders if folder.title == 'Recordings']
    if len(recording) == 0:
        return []
    recordings = upnp.find_directories(cd_ctr, cd_service, recording[0].id)
    return filter_recording_items(options, recordings)


def filter_recording_items(options, recordings):
    """
    Process the returned FetchTV recordings and filter the results as per the provided options.
    """
    results = []
    for recording in recordings:
        result = {'title': recording.title, 'items': []}
        # Skip not matching folders
        if (options.folder and
                not next((include_folder for include_folder in options.folder
                          if recording.title.lower().find(include_folder.strip().lower()) != -1), False)):
            continue
        # Skip excluded folders
        if (options.exclude and
                next((exclude_folder for exclude_folder in options.exclude
                      if recording.title.lower().find(exclude_folder.strip().lower()) != -1), False)):
            continue
        print('\t -- ' + recording.title)

        # Process recorded items
        if not options.shows:  # Only display folders
            for item in recording.items:
                # Skip not matching titles
                if (options.title and
                        not next((include_title for include_title in options.title
                                  if item.title.lower().find(include_title.strip().lower()) != -1), False)):
                    continue
                print('\t\t -- %s (%s)' % (item.title, item.url))
                result['items'].append(item)
            results.append(result)
    return results


def discover_fetch(ip=False, port=FETCHTV_PORT):
    location_urls = upnp.discover_pnp_locations() if not ip else ['http://%s:%i/MediaServer.xml' % (ip, port)]
    locations = upnp.parse_locations(location_urls)
    # Find fetch
    result = [location for location in locations if location.manufacturerURL == 'http://www.fetch.com/']
    if len(result) == 0:
        print('\tERROR: Unable to locate Fetch UPNP service')
        print('[+] Discovery failed')
        return False

    print('[+] Discovery successful: ' + result[0].url)
    return result[0]


def show_help():
    print('''
      Usage:
        fetchtv_upnp.py <command> <options>
        
        e.g.
        --> Display Fetch Server details
        fetchtv_upnp.py --info
        
        --> List all availble recorded shows (doesn't include episodes)
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --shows

        --> List all availble recorded recordings (all shows and episodes)
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --recordings

        --> Save any new recordings to C:\\Temp
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --save="C:\\\\temp"

        --> Save any new recordings to C:\\Temp apart from 2 Broke Girls
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --save="C:\\\\temp" --exclude="2 Broke Girls"

        --> Save any new episodes for the show 2 Broke Girls to C:\\Temp
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --folder="2 Broke Girls" --save="C:\\\\temp"
        
        --> Save episode containing 'S4 E12' for the show 2 Broke Girls to C:\\Temp
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --overwrite --folder="2 Broke Girls" --title="S4 E12" --save="C:\\\\temp"

        --> Save episode containing 'S4 E12' or 'S4 E13' for the show 2 Broke Girls to C:\\Temp
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --overwrite --folder="2 Broke Girls" --title="S4 E12, S4 E13" --save="C:\\\\temp"

        Commands:
        --help       --> Display this help
        --info       --> Attempts auto-discovery and returns the Fetch Servers details
        --recordings --> List or save recordings
        --shows      --> List the names of shows with available recordings

        Options:
        --ip=<ip_address>             --> Specify the IP Address of the Fetch Server, if auto-discovery fails
        --port=<port>                 --> Specify yhe port of the Fetch Server, if auto-discovery fails, normally 49152
        --overwrite                   --> Will save and overwrite any existing files
        --save=<path>                 --> Save recordings to the specified path
        --folder="<text>[,<text>]"    --> Only return recordings where the folder contains the specified text
        --exclude="<text>[,<text>]"   --> Don't download folders containing the specified text
        --title="<text>[,<text>]"     --> Only return recordings where the item contains the specified text
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
            if options.overwrite or not saved_files.contains(item):
                some_to_record = True
                directory = path + os.path.sep + create_valid_filename(show['title'])
                if not os.path.exists(directory):
                    os.makedirs(directory)
                file_path = directory + os.path.sep + create_valid_filename(item.title) + '.mpeg'

                # Check if already writing
                lock_file = file_path + CONST_LOCK
                if os.path.exists(lock_file):
                    print('\t -- Already writing (lock file exists) skipping: [%s]' % item.title)
                    continue

                if download_file(item, file_path):
                    saved_files.add_file(item)

    if not some_to_record:
        print('\t -- There is nothing new to record')


def main(argv):
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

    if options.recordings or options.shows:
        print('[+] List Recordings:')
        recordings = get_fetch_recordings(fetch_server, options)

        if options.save:
            print('[+] Saving Recordings:')
            save_recordings(recordings, options)

    print('[+] Done: %s' % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


if __name__ == "__main__":
    main(sys.argv)
