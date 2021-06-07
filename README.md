# FetchTV-Helpers
Useful tools for FetchTV
Tested with Python 3.7, requires at least Python 3.6.

## fetchtv_upnp.py
I just got my FetchTV and I expected to be able to cast or view recordings on my other devices using the app.
Alas this was not to be.
My workaround is to save the recordings to another filesystem accessible by Plex. Then use Plex to view, cast etc...

By default this script will only save new recordings, it tracks what is aleaded downloaded in the file fetchtv_save_list.json.
You can use the ```--overwrite``` option to override this.

### Install:
Recommended to use Python 3.7 or higher.
Install the required dependencies.

```pip install -r requirements.txt```

### Functions:
- Autodiscover FetchTV DLNA server
- View server information
- List all recordings
- Only save new recordings, or save everything that matches options
- Exclude some recordings from being downloaded 
- Save recordings to a local filesystem
- Save recordings for specific shows or episodes to a local filesystem

### Usage:
        fetchtv_upnp.py <command> <options>
        
        e.g.
        --> Display Fetch Server details
        fetchtv_upnp.py --info
        
        --> List all available recorded shows (doesn't include episodes)
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --shows

        --> List only recordings that haven't been saved
        fetchtv_upnp.py --recordings --new --ip=192.168.1.10 --port=49152

        --> Return responses as JSON
        fetchtv_upnp.py --recordings --json --ip=192.168.1.10 --port=49152

        --> List all available recorded items (all shows and episodes)
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152

        --> Save any new recordings to C:\\Temp
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --save="C:\\temp"

        --> Save any new recordings to C:\\Temp apart from 2 Broke Girls
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --save="C:\\temp" --exclude="2 Broke Girls"

        --> Save any new episodes for the show 2 Broke Girls to C:\\Temp
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --folder="2 Broke Girls" --save="C:\\temp"
        
        --> Save episode containing 'S4 E12' for the show 2 Broke Girls to C:\\Temp
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --overwrite --folder="2 Broke Girls" --title="S4 E12" --save="C:\\temp"

        --> Save episode containing 'S4 E12' or 'S4 E13' for the show 2 Broke Girls to C:\\Temp
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --overwrite --folder="2 Broke Girls" --title="S4 E12, S4 E13" --save="C:\\temp"

        --> List anything currently recrding 
        fetchtv_upnp.py --isrecording --ip=192.168.1.10 --port=49152

        Commands:
        --help        --> Display this help
        --info        --> Attempts auto-discovery and returns the Fetch Servers details
        --recordings  --> List or save recordings
        --shows       --> List the names of shows with available recordings
        --isrecording --> List any items that are currently recording. If no filtering is specified this will scan all
                          items on the Fetch server so it can take some time

        Options:
        --ip=<ip_address>             --> Specify the IP Address of the Fetch Server, if auto-discovery fails
        --port=<port>                 --> Specify yhe port of the Fetch Server, if auto-discovery fails, normally 49152
        --overwrite                   --> Will save and overwrite any existing files
        --save=<path>                 --> Save recordings to the specified path
        --folder="<text>[,<text>]"    --> Only return recordings where the folder contains the specified text
        --exclude="<text>[,<text>]"   --> Don't download folders containing the specified text
        --title="<text>[,<text>]"     --> Only return recordings where the item contains the specified text
        --json                        --> Output show/recording results in JSON, ignored if save option is specified

