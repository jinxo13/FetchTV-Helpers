# FetchTV-Helpers
Useful tools for FetchTV
Tested with Python 2.7 and 3.7

## fetchtv_upnp.py
I just got my FetchTV and I expected to be able to cast or view recordings on my other devices using the app.
Alas this was not to be.

My workaround is to save the recordings to another filesystem accessible by Plex.
Then use Plex to view, cast etc...

### Install:
Recommended to use Python 3.7 or higher.
Install the required dependencies.

```pip install -r requirements.txt```

### Functions:
- Autodiscover FetchTV DLNA server
- View server information
- List all recordings
- Only save new recordings, or save everything that matches options
- Save recordings to a local filesystem
- Save recordings for a show or an episode to a local filesystem

### Usage:
        fetchtv_upnp.py <command> <options>
        
        e.g.
        --> Display Fetch Server details
        fetchtv_upnp.py --info
        
        --> Save any new recordings to C:\\Temp
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --save='C:\\temp'

        --> Save any new episodes for the show '2 Broke Girls' to C:\\Temp
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --folder='2 Broke Girls' --save='C:\\temp'
        
        --> Save episode contianing 'S4 E12' for the show '2 Broke Girls' to C:\\Temp
        fetchtv_upnp.py --recordings --ip=192.168.1.10 --port=49152 --overwrite --folder='2 Broke Girls' --title='S4 E12' --save='C:\\temp'

        Commands:
        --help       --> Display this help
        --info       --> Attempts auto-discovery and returns the Fetch Servers details
        --recordings --> List or save recordings

        Options:
        --ip=<ip_address>  --> Specify the IP Address of the Fetch Server, if auto-discovery fails
        --port=<port>      --> Specify yhe port of the Fetch Server, if auto-discovery fails, normally 49152
        --overwrite        --> Will save and overwrite any existing files
        --save=<path>      --> Save recordings to the specified path
        --folder=<text>    --> Only return recordings where the folder contains the specified text
        --title=<text>     --> Only return recordings where the item contains the specified text

