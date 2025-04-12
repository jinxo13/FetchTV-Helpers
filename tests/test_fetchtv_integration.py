import os
import tempfile
import unittest
from os.path import join, dirname
from dotenv import load_dotenv

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

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

FETCHTV_IP = os.getenv("FETCHTV_IP")
FETCHTV_PORT = int(os.getenv("FETCHTV_PORT"))

VAL_IP = f'{OPTION_IP}={FETCHTV_IP}'
VAL_PORT = f'{OPTION_PORT}={FETCHTV_PORT}'

SHOW_INFO = {"SHOW_ONE": "", "SHOW_TWO": "", "SHOW_ONE_EP_ONE": "", "SHOW_ONE_EP_TWO": ""}


class TestUpnp(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        json_files = SAVE_FOLDER + os.path.sep + fetchtv.SAVE_FILE
        if os.path.exists(json_files):
            os.remove(json_files)
        fetch_server = fetchtv.discover_fetch(ip=FETCHTV_IP, port=FETCHTV_PORT)
        recordings = fetchtv.get_fetch_recordings(fetch_server, fetchtv.Options(''))

        for recording in recordings:
            if len(recording['items']) >= 2 and recording['items'][0].title != recording['items'][1].title:
                SHOW_INFO["SHOW_ONE"] = recording['title']
                SHOW_INFO["SHOW_ONE_EP_ONE"] = recording['items'][0].title
                SHOW_INFO["SHOW_ONE_EP_TWO"] = recording['items'][1].title
            else:
                SHOW_INFO["SHOW_TWO"] = recording['title']
            if SHOW_INFO["SHOW_ONE"] != "" and SHOW_INFO["SHOW_TWO"] != "":
                break

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

        # Default
        fetch_server = fetchtv.discover_fetch()
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
                      f'{OPTION_FOLDER}="{SHOW_INFO["SHOW_ONE"]}"'])

    def test_cmdline_recording_info_exclude(self):
        fetchtv.main([VAL_IP, VAL_PORT, CMD_RECORDINGS,
                      f'{OPTION_EXCLUDE}="{SHOW_INFO["SHOW_ONE"]}"'])

    def test_cmdline_recording_episode(self):
        fetchtv.main([VAL_IP, VAL_PORT, CMD_RECORDINGS,
                      f'{OPTION_FOLDER}="{SHOW_INFO["SHOW_ONE"]}"', f'{OPTION_TITLE}="{SHOW_INFO["SHOW_ONE_EP_ONE"]}"'])

    def test_cmdline_save(self):
        with patch('fetchtv_upnp.download_file', Mock()):
            fetchtv.main(
                [VAL_IP, VAL_PORT, CMD_RECORDINGS, f'{OPTION_SAVE}={SAVE_FOLDER}'])

    def test_cmdline_show_save(self):
        with patch('fetchtv_upnp.download_file', Mock()):
            fetchtv.main([VAL_IP, VAL_PORT, f'{OPTION_FOLDER}="{SHOW_INFO["SHOW_TWO"]}"',
                          CMD_RECORDINGS, f'{OPTION_SAVE}={SAVE_FOLDER}'])

    def test_cmdline_show_save_all(self):
        with patch('fetchtv_upnp.download_file', Mock()):
            fetchtv.main([VAL_IP, VAL_PORT, f'{OPTION_FOLDER}="{SHOW_INFO["SHOW_TWO"]}"',
                          CMD_RECORDINGS, OPTION_OVERWRITE, f'{OPTION_SAVE}={SAVE_FOLDER}'])

    def test_cmdline_show_save_all_json(self):
        with patch('fetchtv_upnp.download_file', Mock()):
            fetchtv.main([VAL_IP, VAL_PORT, f'{OPTION_FOLDER}="{SHOW_INFO["SHOW_TWO"]}"',
                          CMD_RECORDINGS, OPTION_JSON, OPTION_OVERWRITE, f'{OPTION_SAVE}={SAVE_FOLDER}'])

    def test_get_shows_episodes(self):
        fetch_server = fetchtv.discover_fetch(FETCHTV_IP, FETCHTV_PORT)
        results = fetchtv.get_fetch_recordings(
            fetch_server,
            fetchtv.Options([VAL_IP, VAL_PORT,
                             f'{OPTION_FOLDER}="{SHOW_INFO["SHOW_ONE"]}, {SHOW_INFO["SHOW_TWO"]}"',
                             f'{OPTION_TITLE}="{SHOW_INFO["SHOW_ONE_EP_ONE"]}, {SHOW_INFO["SHOW_ONE_EP_TWO"]}"',
                             CMD_RECORDINGS,
                             OPTION_OVERWRITE,
                             f'{OPTION_SAVE}="{SAVE_FOLDER}"']))

        fetchtv.print_recordings(results)
        # Contains both shows
        self.assertTrue(len(list(result for result in results if result['title'].lower() in [SHOW_INFO["SHOW_ONE"].lower(), SHOW_INFO["SHOW_TWO"].lower()])) == 2)

        # Contains both episodes
        items = list(result for result in results if result['title'] == SHOW_INFO["SHOW_ONE"])[0]['items']
        self.assertTrue(len(items) == 2)
        self.assertTrue(len(list(item for item in items if item.title.startswith(SHOW_INFO["SHOW_ONE_EP_ONE"]))) == 1)
        self.assertTrue(len(list(item for item in items if item.title.startswith(SHOW_INFO["SHOW_ONE_EP_TWO"]))) == 1)

    def test_download_shows_episodes(self):
        self.calls = 0
        with patch('fetchtv_upnp.download_file', Mock()):
            fetchtv.main([VAL_IP, VAL_PORT,
                          f'{OPTION_FOLDER}="{SHOW_INFO["SHOW_ONE"]}, {SHOW_INFO["SHOW_TWO"]}"',
                          f'{OPTION_TITLE}="{SHOW_INFO["SHOW_ONE_EP_ONE"]}, {SHOW_INFO["SHOW_ONE_EP_TWO"]}"', CMD_RECORDINGS, OPTION_OVERWRITE, f'{OPTION_SAVE}="{SAVE_FOLDER}"'])
            self.assertEqual(2, fetchtv.download_file.call_count)

    def test_get_episode(self):
        fetch_server = fetchtv.discover_fetch(FETCHTV_IP, FETCHTV_PORT)
        with patch('fetchtv_upnp.download_file', Mock()):
            results = fetchtv.get_fetch_recordings(fetch_server, fetchtv.Options(
                [VAL_IP, VAL_PORT,
                 f'{OPTION_FOLDER}="{SHOW_INFO["SHOW_ONE"]}"',
                 f'{OPTION_TITLE}="{SHOW_INFO["SHOW_ONE_EP_TWO"]}"', CMD_RECORDINGS, OPTION_OVERWRITE, f'{OPTION_SAVE}="{SAVE_FOLDER}"']))

        # Contains 1 show
        self.assertTrue(
            len(list(result for result in results if result['title'] in [SHOW_INFO["SHOW_ONE"]])) == 1)

        # Contains 1 episode
        items = list(result for result in results if result['title'] == SHOW_INFO["SHOW_ONE"])[0]['items']
        self.assertTrue(len(items) == 1)
        self.assertTrue(len(list(item for item in items if item.title.startswith(SHOW_INFO["SHOW_ONE_EP_TWO"]))) == 1)
