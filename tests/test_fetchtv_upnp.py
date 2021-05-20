import unittest
import fetchtv_upnp as fetchtv
from mock import Mock


class TestUpnp(unittest.TestCase):
    FETCHTV_IP = '192.168.1.147'
    FETCHTV_PORT = 49152

    @staticmethod
    def get_server_url():
        return 'http://%s:%i/MediaServer.xml' % (TestUpnp.FETCHTV_IP, TestUpnp.FETCHTV_PORT)

    def test_auto_discovery(self):
        fetch_server = fetchtv.discover_fetch()
        self.assertTrue(fetch_server)

    def test_discovery(self):
        # Bad server
        fetch_server = fetchtv.discover_fetch(ip='127.0.0.1', port=80)
        self.assertFalse(fetch_server)

        # Mock auto discovery
        stash = fetchtv.discover_pnp_locations
        fetchtv.discover_pnp_locations = Mock(return_value=[self.get_server_url()])

        fetch_server = fetchtv.discover_fetch()
        self.assertEqual(fetch_server.url, self.get_server_url())
        fetchtv.discover_pnp_locations.assert_called_once()
        fetchtv.discover_pnp_locations = stash

        # Manual server
        fetch_server = fetchtv.discover_fetch(ip=TestUpnp.FETCHTV_IP, port=TestUpnp.FETCHTV_PORT)
        self.assertTrue(fetch_server)

        # Default port
        fetch_server = fetchtv.discover_fetch(ip=TestUpnp.FETCHTV_IP)
        self.assertTrue(fetch_server)

        # Bad port
        fetch_server = fetchtv.discover_fetch(ip=TestUpnp.FETCHTV_IP, port=80)
        self.assertFalse(fetch_server)

    def test_get_recordings(self):
        fetch_server = fetchtv.discover_fetch(ip=TestUpnp.FETCHTV_IP, port=TestUpnp.FETCHTV_PORT)
        recordings = fetchtv.get_fetch_recordings(fetch_server, fetchtv.Options(''))
        self.assertTrue(recordings)

    def test_cmdline_auto_discovery(self):
        fetchtv.main(['--info'])

    def test_cmdline_help(self):
        fetchtv.main(['--help'])

    def test_cmdline_info(self):
        fetchtv.main(['--ip=' + TestUpnp.FETCHTV_IP, '--port=' + str(TestUpnp.FETCHTV_PORT), '--info'])
        fetchtv.main(['--ip=' + TestUpnp.FETCHTV_IP, '--info'])

    def test_cmdline_recording_info(self):
        fetchtv.main(['--ip=' + TestUpnp.FETCHTV_IP, '--port=' + str(TestUpnp.FETCHTV_PORT), '--recordings'])

    def test_cmdline_shows_info(self):
        fetchtv.main(['--ip=' + TestUpnp.FETCHTV_IP, '--port=' + str(TestUpnp.FETCHTV_PORT), '--shows'])

    def test_cmdline_recording_info_show(self):
        fetchtv.main(['--ip=' + TestUpnp.FETCHTV_IP, '--port=' + str(TestUpnp.FETCHTV_PORT), '--recordings',
                      '--folder="2 Broke Girls"'])

    def test_cmdline_recording_episode(self):
        fetchtv.main(['--ip=' + TestUpnp.FETCHTV_IP, '--port=' + str(TestUpnp.FETCHTV_PORT), '--recordings',
                      '--folder=\'2 Broke Girls\'', '--title=\'S4 E12\''])

    def test_cmdline_save(self):
        fetchtv.download_file = Mock()  # Don't save any files
        fetchtv.main(
            ['--ip=' + TestUpnp.FETCHTV_IP, '--port=' + str(TestUpnp.FETCHTV_PORT), '--recordings', '--save=c:\\temp'])

    def test_cmdline_show_save(self):
        fetchtv.download_file = Mock()  # Don't save any files
        fetchtv.main(['--ip=' + TestUpnp.FETCHTV_IP, '--port=' + str(TestUpnp.FETCHTV_PORT), '--folder="LEGO Masters"',
                      '--recordings', '--save=c:\\temp'])

    def test_cmdline_show_save_all(self):
        fetchtv.download_file = Mock()  # Don't save any files
        fetchtv.main(['--ip=' + TestUpnp.FETCHTV_IP, '--port=' + str(TestUpnp.FETCHTV_PORT), '--folder="LEGO Masters"',
                      '--recordings', '--overwrite', '--save=c:\\temp'])

    def test_cmdline_episode_save(self):
        fetchtv.download_file = Mock()  # Don't save any files
        fetchtv.main(['--ip=' + TestUpnp.FETCHTV_IP, '--port=' + str(TestUpnp.FETCHTV_PORT), '--folder="2 Broke Girls, Lego Masters"',
                      '--title="S4 E13, S4 E12"', '--recordings', '--overwrite', '--save="c:\\temp"'])

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
        self.assertEqual(fetchtv.ts_to_seconds('00:31:27'), 1887)
        self.assertEqual(fetchtv.ts_to_seconds('03:31:27'), 12687)
        self.assertEqual(fetchtv.ts_to_seconds('00:00:00'), 0)
