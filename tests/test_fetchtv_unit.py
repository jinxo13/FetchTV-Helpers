import json
import os
import unittest
import fetchtv_upnp as fetchtv
import tempfile
from mock import Mock, patch, mock_open
import helpers.upnp as upnp

OPTION_IP = '--ip'
OPTION_PORT = '--port'
OPTION_OVERWRITE = '--overwrite'
OPTION_FOLDER = '--folder'
OPTION_TITLE = '--title'
OPTION_EXCLUDE = '--exclude'
OPTION_SAVE = '--save'
OPTION_JSON = '--json'

CMD_RECORDINGS = '--recordings'
CMD_IS_RECORDING = '--isrecording'
CMD_INFO = '--info'
CMD_SHOWS = '--shows'
CMD_HELP = '--help'

URL_DUMMY = 'http://dummy'
URL_NO_RECORDINGS = 'http://no_recordings'

SHOW_ONE = '2 Broke Girls'
SHOW_ONE_EP_ONE = 'S4 E12'
SHOW_ONE_EP_TWO = 'S4 E13'

SHOW_TWO = 'Lego Masters'


def get_file(filename):
    with open(filename, mode='r') as file:
        return file.read()


def mock_get(p_url, timeout=0, stream=False):
    result = Mock()
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock()
    result.iter_content = Mock(return_value='0')
    result.status_code = 200
    # Simulate a recording item
    if p_url == 'http://192.168.1.147:49152/web/903106340':
        result.headers = {'content-length': fetchtv.MAX_OCTET}
    else:
        result.headers = {'content-length': 5}

    response_dir = os.path.dirname(__file__) + os.path.sep + 'responses' + os.path.sep
    if p_url.endswith('cds.xml'):
        result.text = get_file(response_dir + 'fetch_cds.xml')
    else:
        result.text = get_file(response_dir + 'fetch_info.xml')
    return result


def mock_get_recording(p_url, timeout=0, stream=False):
    result = Mock()
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock()
    result.iter_content = Mock(return_value='0')
    result.status_code = 200
    result.headers = {'content-length': fetchtv.MAX_OCTET}
    response_dir = os.path.dirname(__file__) + os.path.sep + 'responses' + os.path.sep
    if p_url.endswith('cds.xml'):
        result.text = get_file(response_dir + 'fetch_cds.xml')
    else:
        result.text = get_file(response_dir + 'fetch_info.xml')
    return result


def mock_post(p_url, data, headers):
    result = Mock()
    result.__enter__ = Mock()
    result.__exit__ = Mock()
    result.status_code = 200

    response_dir = os.path.dirname(__file__) + os.path.sep + 'responses' + os.path.sep
    if data.find('<ObjectID>61</ObjectID>') != -1:
        result.text = get_file(response_dir + 'fetch_recording_items.xml')
    elif data.find('<ObjectID>0</ObjectID>') != -1:
        if p_url.startswith(URL_NO_RECORDINGS):
            result.text = get_file(response_dir + 'fetch_no_recordings.xml')
        else:
            result.text = get_file(response_dir + 'fetch_base_folders.xml')
    else:
        result.text = get_file(response_dir + 'fetch_recording_folders.xml')
    return result


@patch('requests.get', mock_get)
@patch('requests.post', mock_post)
class TestOptions(unittest.TestCase):

    def test_command_order(self):
        # Command precedence is help, info, recordings, shows
        options = fetchtv.Options([CMD_INFO, CMD_RECORDINGS, CMD_SHOWS, CMD_HELP])
        self.assertTrue(options.help)
        # Use first valid command
        self.assertFalse(options.recordings)
        self.assertFalse(options.shows)
        self.assertFalse(options.info)

        options = fetchtv.Options([CMD_SHOWS, CMD_RECORDINGS, CMD_INFO])
        self.assertTrue(options.info)
        # Use first valid command
        self.assertFalse(options.help)
        self.assertFalse(options.recordings)
        self.assertFalse(options.shows)

        options = fetchtv.Options([CMD_SHOWS, CMD_RECORDINGS])
        self.assertTrue(options.shows)
        # Use first valid command
        self.assertFalse(options.help)
        self.assertFalse(options.info)
        self.assertFalse(options.recordings)

    def test_command_values(self):
        options = fetchtv.Options([f'{CMD_HELP}=fred'])
        self.assertTrue(options.help)

    def test_option_multi_value(self):
        # Support multiple values
        for option in [OPTION_FOLDER, OPTION_TITLE, OPTION_EXCLUDE]:
            option = option.strip('-')
            options = fetchtv.Options([f'--{option}="wibble"'])
            self.assertEqual(options.__getattribute__(option), ['wibble'])

            options = fetchtv.Options([f'--{option}="wibble, wobble, rabble"'])
            self.assertEqual(options.__getattribute__(option), ['wibble', 'wobble', 'rabble'])

    def test_option_strip_quotes(self):
        options = fetchtv.Options([f'{CMD_INFO}="fred"'])
        self.assertEqual(True, options.info)

        options = fetchtv.Options([f'{CMD_INFO}=\'fred\''])
        self.assertEqual(True, options.info)

    def test_option_strip_save(self):
        options = fetchtv.Options([f'{OPTION_SAVE}]=fred' + os.path.sep])
        self.assertEqual(options.save, 'fred')

    def test_option_single_value(self):
        # Support multiple values
        for option in [OPTION_SAVE, OPTION_IP, OPTION_PORT]:
            option = option.strip('-')
            options = fetchtv.Options([f'--{option}="wibble"'])
            self.assertEqual(options.__getattribute__(option), 'wibble')

            options = fetchtv.Options([f'--{option}="wibble, wobble, rabble"'])
            self.assertEqual(options.__getattribute__(option), 'wibble, wobble, rabble')


@patch('requests.get', mock_get)
@patch('requests.post', mock_post)
class TestGetFetchRecordings(unittest.TestCase):

    def test_get_shows(self):
        fetch_server = Mock()
        fetch_server.url = URL_DUMMY
        options = fetchtv.Options([CMD_SHOWS])
        results = fetchtv.get_fetch_recordings(fetch_server, options)
        fetchtv.print_recordings(results)
        self.assertEqual(8, len(results))

    def test_get_shows_json(self):
        fetch_server = Mock()
        fetch_server.url = URL_DUMMY
        options = fetchtv.Options([CMD_SHOWS, OPTION_JSON])
        results = fetchtv.get_fetch_recordings(fetch_server, options)
        output = fetchtv.print_recordings(results)
        output = json.loads(output)
        self.assertEqual(8, len(output))

    def test_no_recordings_folder(self):
        fetch_server = Mock()
        fetch_server.url = URL_NO_RECORDINGS
        options = fetchtv.Options([CMD_RECORDINGS])
        results = fetchtv.get_fetch_recordings(fetch_server, options)
        fetchtv.print_recordings(results)
        self.assertEqual(0, len(results))

    def test_get_all_recordings(self):
        fetch_server = Mock()
        fetch_server.url = URL_DUMMY
        options = fetchtv.Options([CMD_RECORDINGS])
        results = fetchtv.get_fetch_recordings(fetch_server, options)
        fetchtv.print_recordings(results)
        self.assertEqual(8, len(results))
        self.assertEqual(134, len(results[4]['items']))

    def test_get_all_recordings_json(self):
        fetch_server = Mock()
        fetch_server.url = URL_DUMMY
        options = fetchtv.Options([CMD_RECORDINGS, OPTION_JSON])
        results = fetchtv.get_fetch_recordings(fetch_server, options)
        output = fetchtv.print_recordings(results)
        output = json.loads(output)
        self.assertEqual(8, len(output))
        self.assertEqual(134, len(output[4]['items']))

    def test_get_recordings_items_json(self):
        fetch_server = Mock()
        fetch_server.url = URL_DUMMY
        options = fetchtv.Options([CMD_IS_RECORDING, OPTION_JSON])
        results = fetchtv.get_fetch_recordings(fetch_server, options)
        output = fetchtv.print_recordings(results)
        output = json.loads(output)
        self.assertEqual(1, len(output))
        self.assertEqual(1, len(output[0]['items']))

    def test_exclude_one_show(self):
        fetch_server = Mock()
        fetch_server.url = URL_DUMMY
        options = fetchtv.Options([CMD_RECORDINGS,
                                   f'{OPTION_EXCLUDE}="{SHOW_ONE}"'])
        results = fetchtv.get_fetch_recordings(fetch_server, options)
        fetchtv.print_recordings(results)
        self.assertEqual(7, len(results))

    def test_exclude_two_shows(self):
        fetch_server = Mock()
        fetch_server.url = URL_DUMMY
        options = fetchtv.Options([CMD_RECORDINGS,
                                   f'{OPTION_EXCLUDE}="{SHOW_ONE}, {SHOW_TWO}"'])
        results = fetchtv.get_fetch_recordings(fetch_server, options)
        fetchtv.print_recordings(results)
        self.assertEqual(5, len(results))  # Test data has LEGO Masters and Lego Masters - both are matched

    def test_get_one_show_recording(self):
        fetch_server = Mock()
        fetch_server.url = URL_DUMMY
        options = fetchtv.Options([CMD_RECORDINGS,
                                   f'{OPTION_FOLDER}="{SHOW_ONE}"'])
        results = fetchtv.get_fetch_recordings(fetch_server, options)
        fetchtv.print_recordings(results)
        self.assertEqual(1, len(results))
        self.assertEqual(134, len(results[0]['items']))

    def test_get_two_show_recording(self):
        fetch_server = Mock()
        fetch_server.url = URL_DUMMY
        options = fetchtv.Options([CMD_RECORDINGS,
                                   f'{OPTION_FOLDER}="{SHOW_ONE}, {SHOW_TWO}"'])
        results = fetchtv.get_fetch_recordings(fetch_server, options)
        fetchtv.print_recordings(results)
        self.assertEqual(3, len(results))  # Test data returns LEGO Masters and Lego Masters....

    def test_get_one_recording_item(self):
        fetch_server = Mock()
        fetch_server.url = URL_DUMMY
        options = fetchtv.Options([CMD_RECORDINGS,
                                   f'{OPTION_FOLDER}="{SHOW_ONE}"',
                                   f'{OPTION_TITLE}="{SHOW_ONE_EP_ONE}"'])
        results = fetchtv.get_fetch_recordings(fetch_server, options)
        fetchtv.print_recordings(results)
        self.assertEqual(1, len(results))
        self.assertEqual(1, len(results[0]['items']))

    def test_get_two_recording_item(self):
        fetch_server = Mock()
        fetch_server.url = URL_DUMMY
        options = fetchtv.Options([CMD_RECORDINGS,
                                   f'{OPTION_FOLDER}="{SHOW_ONE}"',
                                   f'{OPTION_TITLE}="{SHOW_ONE_EP_ONE}, {SHOW_ONE_EP_TWO}"'])
        results = fetchtv.get_fetch_recordings(fetch_server, options)
        fetchtv.print_recordings(results)
        self.assertEqual(1, len(results))
        self.assertEqual(2, len(results[0]['items']))


class TestSaveRecordings(unittest.TestCase):
    pass


@patch('requests.get', mock_get)
class TestDownloadFile(unittest.TestCase):

    def test_save_item(self):
        # Test download works when item is not recording

        temp_dir = tempfile.gettempdir()
        temp_file = f'{temp_dir}{os.path.sep}test.txt'

        mock_file = mock_open(read_data='xxx')
        mock_location = Mock()
        mock_location.url = URL_DUMMY
        with patch('requests.get', mock_get):
            with patch('fetchtv_upnp.open', mock_file):
                with patch('fetchtv_upnp.os.rename', Mock()):
                    self.assertTrue(fetchtv.download_file(mock_location, temp_file))

        # Test download skips when item is recording
        with patch('requests.get', mock_get_recording):
            with patch('fetchtv_upnp.open', mock_file):
                with patch('fetchtv_upnp.os.rename', Mock()):
                    self.assertFalse(fetchtv.download_file(mock_location, temp_file))

    def test_lock_file_writing(self):
        temp_dir = tempfile.gettempdir()
        temp_file = f'{temp_dir}{os.path.sep}test.txt'
        try:
            with open(f'{temp_file}.lock', 'x') as f:
                f.write('.')
            mock_location = Mock()
            mock_location.url = URL_DUMMY
            with patch('requests.get', mock_get):
                self.assertFalse(fetchtv.download_file(mock_location, temp_file))
        finally:
            os.remove(f'{temp_file}.lock')


class TestUtils(unittest.TestCase):

    def test_valid_filename(self):
        # Special characters and spaces
        self.assertEqual(fetchtv.create_valid_filename('my:file'), 'myfile')
        self.assertEqual(fetchtv.create_valid_filename('my:>file'), 'myfile')
        self.assertEqual(fetchtv.create_valid_filename('my:> file'), 'my_file')
        self.assertEqual(fetchtv.create_valid_filename('my&*^file '), 'my&^file')
        self.assertEqual(fetchtv.create_valid_filename('my\tfile '), 'my_file')

        # Max file length is 255 characters
        self.assertEqual(len(fetchtv.create_valid_filename('abc' * 85)), 255)
        self.assertEqual(len(fetchtv.create_valid_filename('abc' * 86)), 255)

    def test_ts_to_seconds(self):
        self.assertEqual(upnp.ts_to_seconds('00:31:27'), 1887)
        self.assertEqual(upnp.ts_to_seconds('03:31:27'), 12687)
        self.assertEqual(upnp.ts_to_seconds('00:00:00'), 0)
