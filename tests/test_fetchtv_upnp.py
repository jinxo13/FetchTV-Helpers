import unittest
import fetchtv_upnp as fetchtv

class TestUpnp(unittest.TestCase):

    def test_discovery(self):
        #Discover Fetch Sever, or allow supplying to command line
        fetch_server = fetchtv.discover_fetch(ip='127.0.0.1', port=80)
        self.assertFalse(fetch_server)

        fetch_server = fetchtv.discover_fetch(ip='192.168.1.147', port=49152)
        self.assertTrue(fetch_server != False)

    def test_get_recordings(self):
        fetch_server = fetchtv.discover_fetch(ip='192.168.1.147', port=49152)
        recordings = fetchtv.get_fetch_recordings(fetch_server)
        self.assertTrue(recordings != False)

    def test_help(self):
        fetchtv.main(['--help'])

    def test_info(self):
        fetchtv.main(['--ip=192.168.1.147', '--port=49152', '--info'])
        fetchtv.main(['--ip=192.168.1.147', '--info'])

    def test_auto_discovery(self):
        fetchtv.main([])

    def test_recording_info(self):
        fetchtv.main(['--ip=192.168.1.147', '--port=49152', '--recordings'])
        fetchtv.main(['--ip=192.168.1.147', '--port=49152', '--recordings', '--folder="2 Broke Girls"'])

    def test_save(self):
        fetchtv.main(['--ip=192.168.1.147', '--port=49152', '--recordings', '--save=c:\\temp'])

    def test_show_save(self):
        fetchtv.main(['--ip=192.168.1.147', '--port=49152', '--folder="2 Broke Girls"', '--recordings', '--save=c:\\temp'])

    def test_valid_filename(self):
        self.assertEqual(fetchtv.create_valid_filename('my:file'), 'myfile')
