# FetchTV-Helpers
Useful tools for FetchTV
Tested with Python 2.7 and 3.7

## fetchtv_upnp.py
I just got my FetchTV and I expected to be able to cast or view recordings on my other devices using the app.
Alas this was not to be.

My workaround is to save the recordings to another filesystem accessible by Plex.
Then use Plex to view, cast etc...

### Functions:
- Autodiscover FetchTV DLNA server
- View server information
- List all recordings
- Save recordings to a local filesystem

### Usage:
```
fetchtv_upnp.py --help
 --> Displays this help

fetchtv_upnp.py --info
-->  Attempts auto-discovery and returns the Fetch Servers details

3.10 Abercrombie release
fetchtv_upnp.py --ip=192.168.1.100 --port=49153
--> Returns the Fetch Servers details for the specified ip/port

Previous release
fetchtv_upnp.py --ip=192.168.1.100 --port=49152
--> Returns the Fetch Servers details for the specified ip/port


fetchtv_upnp.py --recordings
-->  Returns the list of all recordings

fetchtv_upnp.py --recordings --save=<path>
-->  Saves all recordings to the specified path, if they haven't already been copied

fetchtv_upnp.py --recordings --folder='2 Broke Girls' --save=<path>
-->  Saves recordings for the specified folder to the specified path, if they haven't already been copied
