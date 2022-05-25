import re
import socket
import requests
import xml.etree.ElementTree as ElementTree

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

DISCOVERY_TIMEOUT = 3
REQUEST_TIMEOUT = 5
NO_NUMBER_DEFAULT = ''


class UpnpError(Exception):
    def __init__(self, msg):
        super().__init__(msg)


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

    def __init__(self, xml):
        self.type = xml.find("./{urn:schemas-upnp-org:metadata-1-0/upnp/}class").text
        self.title = xml.find("./{http://purl.org/dc/elements/1.1/}title").text
        self.id = get_xml_attr(xml, 'id', NO_NUMBER_DEFAULT)
        self.parent_id = get_xml_attr(xml, 'parentID', NO_NUMBER_DEFAULT)
        self.description = xml.find("./{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}description")
        self.description = self.description.text if self.description is not None else ''
        res = xml.find("./{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}res")
        self.url = res.text
        self.size = int(get_xml_attr(res, 'size', NO_NUMBER_DEFAULT))
        self.duration = ts_to_seconds(get_xml_attr(res, 'duration', '0'))
        self.parent_name = get_xml_attr(res, 'parentTaskName')


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
    except socket.timeout:
        return locations
    except socket.error as err:
        raise UpnpError(msg=f'A socket error occurred, Error: {err}')
    finally:
        sock.close()


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
                except ElementTree.ParseError as err:
                    raise UpnpError(msg=f'XML Parsing failed for location {location}, Error: {err.msg}')

                loc = Location(location, xml_root)
                result.append(loc)

            except requests.exceptions.ConnectionError as err:
                raise UpnpError(msg=f'Connection Error, could not load {location}, Error: {err}')
            except requests.exceptions.ReadTimeout:
                raise UpnpError(msg=f'Timeout reading from {location}')
    return result


def get_services(location):
    parsed = urlparse(location.url)
    resp = requests.get(location.url, timeout=REQUEST_TIMEOUT)
    try:
        xml_root = ElementTree.fromstring(resp.text)
    except Exception as err:
        raise UpnpError(msg=f'XML parsing failed for location: {location}, Error: {err.msg}')

    result = {}

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
                result['service_url'] = service_url
                result['cd_ctr'] = parsed.scheme + "://" + parsed.netloc + service.find(
                    './{urn:schemas-upnp-org:device-1-0}controlURL').text
                result['cd_service'] = service.find('./{urn:schemas-upnp-org:device-1-0}serviceType').text
                break
    return result


def find_directories(api_service, object_id='0'):
    """
    Send a 'Browse' request for the top level directory. We will print out the
    top level containers that we observer. I've limited the count to 10.

    @param p_url the url to send the SOAPAction to
    @param p_service the service in charge of this control URI
    """
    p_url = api_service['cd_ctr']
    p_service = api_service['cd_service']
    result = []
    payload = (
        f'''
            <?xml version="1.0" encoding="utf-8" standalone="yes"?>
            <s:Envelope s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/" xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
            <s:Body>
            <u:Browse xmlns:u="{p_service}">
            <ObjectID>{object_id}</ObjectID>
            <BrowseFlag>BrowseDirectChildren</BrowseFlag>
            <Filter>*</Filter>
            <StartingIndex>0</StartingIndex>
            <SortCriteria></SortCriteria>
            </u:Browse>
            </s:Body>
            </s:Envelope>
            ''')

    soap_action_header = {
        'Soapaction': f'"{p_service}#Browse"',
        'Content-type': 'text/xml;charset="utf-8"'
    }

    resp = requests.post(p_url, data=payload, headers=soap_action_header)
    if resp.status_code != 200:
        raise UpnpError(msg=f'Request failed with status: {resp.status_code}')

    xml_root = ElementTree.fromstring(resp.text)
    containers = xml_root.find(".//*Result").text
    if not containers:
        return result

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
    payload = (
        f'''
            <?xml version="1.0" encoding="utf-8" standalone="yes"?>
            <s:Envelope s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/" xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
            <s:Body>
            <u:Browse xmlns:u="{p_service}">
            <ObjectID>{object_id}</ObjectID>
            <BrowseFlag>BrowseDirectChildren</BrowseFlag>
            <Filter>*</Filter>
            <StartingIndex>0</StartingIndex>
            <SortCriteria></SortCriteria>
            </u:Browse>
            </s:Body>
            </s:Envelope>
            ''')
    soap_action_header = {
        'Soapaction': f'"{p_service}#Browse"',
        'Content-type': 'text/xml;charset="utf-8"'
    }

    resp = requests.post(p_url, data=payload, headers=soap_action_header)
    if resp.status_code != 200:
        raise UpnpError(msg=f'Request failed with status: {resp.status_code}')

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
