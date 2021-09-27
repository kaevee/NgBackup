#!/usr/bin/env python3.9
from ngremote import NgRemote
from ngbackup import NgBackup
import logging
from pathlib import Path
import os
import sys
import psutil

working_directory = Path(os.getcwd())
pidfile = working_directory / 'ngbackup.pid'

def is_running() -> bool:
    if pidfile.exists():
        f = open(pidfile, 'r')        
        pid = int(f.readline().strip('\n'))
        f.close()

        try:
            p = psutil.Process(pid)
        except Exception:
            # We have encountered a stale pidfile. Probably the script was interrupted
            backup.logger.log(logging.INFO, "Process with ID: %d is not running. Review log files from previous run", pid)
            os.unlink(pidfile)      
            return False
        else:
            return True
    else:
        return False

backup = NgBackup()

if is_running():
    backup.logger.log(logging.INFO, "Only one instance can be run at one time. Exiting")
    sys.exit()
else:
    str_pid = str(os.getpid())
    f = open(pidfile, 'w')
    f.write(str_pid)
    f.close()

backup.run()
os.unlink(pidfile)