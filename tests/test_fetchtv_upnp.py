import unittest
import fetchtv_upnp as fetchtv
from mock import Mock

class TestUpnp(unittest.TestCase):

    FETCHTV_IP='192.168.1.147'
    FETCHTV_PORT=49152

    @staticmethod
    def get_server_url():
        return 'http://%s:%i/MediaServer.xml' % (TestUpnp.FETCHTV_IP, TestUpnp.FETCHTV_PORT)

    def test_discovery(self):
        #Bad server
        fetch_server = fetchtv.discover_fetch(ip='127.0.0.1', port=80)
        self.assertFalse(fetch_server)

        #Mock auto discovery
        stash = fetchtv.discover_pnp_locations
        fetchtv.discover_pnp_locations = Mock(return_value=[self.get_server_url()])
        
        fetch_server = fetchtv.discover_fetch()
        self.assertEqual(fetch_server.url, self.get_server_url())
        fetchtv.discover_pnp_locations.assert_called_once()
        fetchtv.discover_pnp_locations = stash

        #Manual server
        fetch_server = fetchtv.discover_fetch(ip=TestUpnp.FETCHTV_IP, port=TestUpnp.FETCHTV_PORT)
        self.assertTrue(fetch_server != False)

        #Default port
        fetch_server = fetchtv.discover_fetch(ip=TestUpnp.FETCHTV_IP)
        self.assertTrue(fetch_server != False)

        #Bad port
        fetch_server = fetchtv.discover_fetch(ip=TestUpnp.FETCHTV_IP, port=80)
        self.assertFalse(fetch_server)

    def test_get_recordings(self):
        fetch_server = fetchtv.discover_fetch(ip=TestUpnp.FETCHTV_IP, port=TestUpnp.FETCHTV_PORT)
        recordings = fetchtv.get_fetch_recordings(fetch_server)
        self.assertTrue(recordings != False)

    def test_cmdline_auto_discovery(self):
        fetchtv.main([])

    def test_cmdline_help(self):
        fetchtv.main(['--help'])

    def test_cmdline_info(self):
        fetchtv.main(['--ip='+TestUpnp.FETCHTV_IP, '--port='+str(TestUpnp.FETCHTV_PORT), '--info'])
        fetchtv.main(['--ip='+TestUpnp.FETCHTV_IP, '--info'])

    def test_cmdline_recording_info(self):
        fetchtv.main(['--ip='+TestUpnp.FETCHTV_IP, '--port='+str(TestUpnp.FETCHTV_PORT), '--recordings'])
        fetchtv.main(['--ip='+TestUpnp.FETCHTV_IP, '--port='+str(TestUpnp.FETCHTV_PORT), '--recordings', '--folder="2 Broke Girls"'])

    def test_cmdline_save(self):
        fetchtv.download_file = Mock() #Don't save any files
        fetchtv.main(['--ip='+TestUpnp.FETCHTV_IP, '--port='+str(TestUpnp.FETCHTV_PORT), '--recordings', '--save=c:\\temp'])

    def test_cmdline_show_save(self):
        fetchtv.download_file = Mock() #Don't save any files
        fetchtv.main(['--ip='+TestUpnp.FETCHTV_IP, '--port='+str(TestUpnp.FETCHTV_PORT), '--folder="2 Broke Girls"', '--recordings', '--save=c:\\temp'])

    def test_valid_filename(self):
        self.assertEqual(fetchtv.create_valid_filename('my:file'), 'myfile')
        self.assertEqual(fetchtv.create_valid_filename('my:>file'), 'myfile')
        self.assertEqual(fetchtv.create_valid_filename('my:> file'), 'my_file')
        self.assertEqual(fetchtv.create_valid_filename('my&*^file '), 'my&^file')
        self.assertEqual(fetchtv.create_valid_filename('my\tfile '), 'my_file')
