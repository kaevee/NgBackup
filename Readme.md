## Rsync Incremental Backup Script 
### Features
* User defined backup intervals
* User defined backup rotations per interval.
   * Example, one can keep 24 hourly backups and 30 daily backups
* Uses hard links to save space across backup intervals
* Cross Platform (Windows, Linux, MacOs, FreeBSD). Requires CygWin for windows
* Transparent drive letter tranlation for CygWin, when source/destination is windows allowing one to use windows paths. For example
    * Source: "C:\Users\UserName\Documents\SharedDevel"
    * Destination: "user@host:C:\Users\UserName\Documents"
* Easy and flexible configuration
    * File Name, whichever is found first in the following order
        * hostname-devel.ini
        * hostname.ini
        * ngbackup.in
    * "hostname.ini" convention allows administrators to run the script on multiple systems and maintain configurations in one single repository
    * Unique SSH key per host
    * Custom backup folder name

### Installation
* The script is tested with Python 3.9
    * Key module requirements
        * Pathlib
    * Third Party Modules required
        * paramkio http://www.paramiko.org/
        * psutil https://github.com/giampaolo/psutil
* For Windows, you need to install Cygwin https://www.cygwin.com/
    * Additional packages required
        * rsync
        * openssh        
* Checkout the repository
* Setup configuration file as required
* Execute NgMain.py script

### Work in Progress
* Notifications by email
* Select intervals for each backup task
* Threading to run backups in parallel
    * Configurable maximum threads
    * Configurable threads per host
* Maximum disk utilization limit per source/target

### Notes
* Code has been tested on Windows/linux with multiple targets
    * Windows -> Windows (Different drive. For example, an external drive)
    * Windows -> Remote *NIX
    * Windows -> Remote Windows
    * *NIX -> *NIX (Local path)
    * *NIx -> Remote *NIX
    * *NIX -> Windows




 
