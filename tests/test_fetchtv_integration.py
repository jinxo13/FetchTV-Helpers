import os
import tempfile
import unittest
import fetchtv_upnp as fetchtv
from mock import Mock, patch

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


# Local settings to test
# Change these to valid settings to test local integration
SAVE_FOLDER = tempfile.gettempdir()

FETCHTV_IP = '192.168.1.147'
FETCHTV_PORT = 49152

SHOW_ONE = '2 Broke Girls'
SHOW_ONE_EP_ONE = 'S4 E12'
SHOW_ONE_EP_TWO = 'S4 E13'
SHOW_TWO = 'Lego Masters'

VAL_IP = f'{OPTION_IP}={FETCHTV_IP}'
VAL_PORT = f'{OPTION_PORT}={FETCHTV_PORT}'


class TestUpnp(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        json_files = SAVE_FOLDER + os.path.sep + fetchtv.SAVE_FILE
        if os.path.exists(json_files):
            os.remove(json_files)

    @staticmethod
    def get_server_url():
        return 'http://%s:%i/MediaServer.xml' % (FETCHTV_IP, FETCHTV_PORT)

    def test_auto_discovery(self):
        fetch_server = fetchtv.discover_fetch()
        self.assertTrue(fetch_server)

    def test_discovery(self):
        # Bad server
        fetch_server = fetchtv.discover_fetch(ip='127.0.0.1', port=80)
        self.assertFalse(fetch_server)

        # Mock auto discovery
        with patch('helpers.upnp.discover_pnp_locations', Mock(return_value=[self.get_server_url()])):
            fetch_server = fetchtv.discover_fetch()
            self.assertEqual(fetch_server.url, self.get_server_url())
            fetchtv.upnp.discover_pnp_locations.assert_called_once()

        # Mock auto discovery
        with patch('helpers.upnp.discover_pnp_locations', Mock(return_value=[])):
            fetch_server = fetchtv.discover_fetch()
            self.assertIsNone(fetch_server)
            fetchtv.upnp.discover_pnp_locations.assert_called_once()

        # Manual server
        fetch_server = fetchtv.discover_fetch(ip=FETCHTV_IP, port=FETCHTV_PORT)
        self.assertTrue(fetch_server)

        # Default port
        fetch_server = fetchtv.discover_fetch(ip=FETCHTV_IP)
        self.assertTrue(fetch_server)

        # Bad port
        fetch_server = fetchtv.discover_fetch(ip=FETCHTV_IP, port=80)
        self.assertFalse(fetch_server)

    def test_get_recordings(self):
        fetch_server = fetchtv.discover_fetch(ip=FETCHTV_IP, port=FETCHTV_PORT)
        recordings = fetchtv.get_fetch_recordings(fetch_server, fetchtv.Options(''))
        self.assertTrue(recordings)

    def test_cmdline_auto_discovery(self):
        fetchtv.main([CMD_INFO])

    def test_cmdline_help(self):
        fetchtv.main(['--help'])

    def test_cmdline_info(self):
        fetchtv.main([VAL_IP, VAL_PORT, CMD_INFO])
        fetchtv.main([VAL_IP, CMD_INFO])

    def test_cmdline_recording_info(self):
        fetchtv.main([VAL_IP, VAL_PORT, CMD_RECORDINGS])

    def test_cmdline_recording_info_json(self):
        fetchtv.main([VAL_IP, VAL_PORT, CMD_RECORDINGS, OPTION_JSON])

    def test_cmdline_anything_recording(self):
        fetchtv.main([VAL_IP, VAL_PORT, CMD_IS_RECORDING, OPTION_JSON])

    def test_cmdline_shows_info(self):
        fetchtv.main([VAL_IP, VAL_PORT, CMD_SHOWS])

    def test_cmdline_recording_info_show(self):
        fetchtv.main([VAL_IP, VAL_PORT, CMD_RECORDINGS,
                      f'{OPTION_FOLDER}="{SHOW_ONE}"'])

    def test_cmdline_recording_info_exclude(self):
        fetchtv.main([VAL_IP, VAL_PORT, CMD_RECORDINGS,
                      f'{OPTION_EXCLUDE}="{SHOW_ONE}"'])

    def test_cmdline_recording_episode(self):
        fetchtv.main([VAL_IP, VAL_PORT, CMD_RECORDINGS,
                      f'{OPTION_FOLDER}="{SHOW_ONE}"', f'{OPTION_TITLE}="{SHOW_ONE_EP_ONE}"'])

    def test_cmdline_save(self):
        with patch('fetchtv_upnp.download_file', Mock()):
            fetchtv.main(
                [VAL_IP, VAL_PORT, CMD_RECORDINGS, f'{OPTION_SAVE}={SAVE_FOLDER}'])

    def test_cmdline_show_save(self):
        with patch('fetchtv_upnp.download_file', Mock()):
            fetchtv.main([VAL_IP, VAL_PORT, f'{OPTION_FOLDER}="{SHOW_TWO}"',
                          CMD_RECORDINGS, f'{OPTION_SAVE}={SAVE_FOLDER}'])

    def test_cmdline_show_save_all(self):
        with patch('fetchtv_upnp.download_file', Mock()):
            fetchtv.main([VAL_IP, VAL_PORT, f'{OPTION_FOLDER}="{SHOW_TWO}"',
                          CMD_RECORDINGS, OPTION_OVERWRITE, f'{OPTION_SAVE}={SAVE_FOLDER}'])

    def test_cmdline_show_save_all_json(self):
        with patch('fetchtv_upnp.download_file', Mock()):
            fetchtv.main([VAL_IP, VAL_PORT, f'{OPTION_FOLDER}="{SHOW_TWO}"',
                          CMD_RECORDINGS, OPTION_JSON, OPTION_OVERWRITE, f'{OPTION_SAVE}={SAVE_FOLDER}'])

    def test_get_shows_episodes(self):
        fetch_server = fetchtv.discover_fetch(FETCHTV_IP, FETCHTV_PORT)
        results = fetchtv.get_fetch_recordings(
            fetch_server,
            fetchtv.Options([VAL_IP, VAL_PORT,
                             f'{OPTION_FOLDER}="{SHOW_ONE}, {SHOW_TWO}"',
                             f'{OPTION_TITLE}="{SHOW_ONE_EP_ONE}, {SHOW_ONE_EP_TWO}"',
                             CMD_RECORDINGS,
                             OPTION_OVERWRITE,
                             f'{OPTION_SAVE}="{SAVE_FOLDER}"']))

        fetchtv.print_recordings(results)
        # Contains both shows
        self.assertTrue(len(list(result for result in results if result['title'] in [SHOW_ONE, SHOW_TWO])) == 2)

        # Contains both episodes
        items = list(result for result in results if result['title'] == SHOW_ONE)[0]['items']
        self.assertTrue(len(items) == 2)
        self.assertTrue(len(list(item for item in items if item.title.startswith(SHOW_ONE_EP_ONE))) == 1)
        self.assertTrue(len(list(item for item in items if item.title.startswith(SHOW_ONE_EP_TWO))) == 1)

    def test_download_shows_episodes(self):
        self.calls = 0
        with patch('fetchtv_upnp.download_file', Mock()):
            fetchtv.main([VAL_IP, VAL_PORT,
                          f'{OPTION_FOLDER}="{SHOW_ONE}, {SHOW_TWO}"',
                          f'{OPTION_TITLE}="{SHOW_ONE_EP_ONE}, {SHOW_ONE_EP_TWO}"', CMD_RECORDINGS, OPTION_OVERWRITE, f'{OPTION_SAVE}="{SAVE_FOLDER}"'])
            self.assertEqual(2, fetchtv.download_file.call_count)

    def test_get_episode(self):
        fetch_server = fetchtv.discover_fetch(FETCHTV_IP, FETCHTV_PORT)
        with patch('fetchtv_upnp.download_file', Mock()):
            results = fetchtv.get_fetch_recordings(fetch_server, fetchtv.Options(
                [VAL_IP, VAL_PORT,
                 f'{OPTION_FOLDER}="{SHOW_ONE}"',
                 f'{OPTION_TITLE}="{SHOW_ONE_EP_TWO}"', CMD_RECORDINGS, OPTION_OVERWRITE, f'{OPTION_SAVE}="{SAVE_FOLDER}"']))

        # Contains 1 show
        self.assertTrue(
            len(list(result for result in results if result['title'] in [SHOW_ONE])) == 1)

        # Contains 1 episode
        items = list(result for result in results if result['title'] == SHOW_ONE)[0]['items']
        self.assertTrue(len(items) == 1)
        self.assertTrue(len(list(item for item in items if item.title.startswith(SHOW_ONE_EP_TWO))) == 1)
