from ngtask import NgTask
from interval import Interval
from pathlib import Path
import os
import re
import sys
import logging
import platform
from configparser import ConfigParser, ExtendedInterpolation
from ngutil import NgUtil

class NgConfig:
    __config = ConfigParser(interpolation=ExtendedInterpolation())
    # region default parameters
    default_inc_name_template: str = "%Y%m%d_%H%M%S"
    default_ssh_key: Path
    cygwin_home: Path
    ssh_bin: Path
    rsync_bin: Path
    # endregion
    logger = logging.getLogger("NgBackup.Config")
    intervals: dict[str, Interval] = {}
    host_key: dict[str, Path] = {}
    rsync_tasks: dict[str, NgTask] = {}
    notification_emails: dict[str, str] = {}
    task_emails: dict[str, list] = {}

    def __init__(self) -> None:                
        self.setup_config_parser()
        self.__read_defaults()
        self.__init_intervals()
        self.__init_inc_name_templates()
        self.__init_host_keys()
        self.__init_sync_tasks()
        self.__init_notification_emails()
        self.__init_task_emails()

    def setup_config_parser(self):
        working_directory = Path(os.getcwd())
        host_name = platform.node().lower()
        config_file = None
        if Path(f"{host_name}.devel.ini").exists():
            config_file = working_directory / f"{host_name}.devel.ini"
        elif Path(f"{host_name}.ini").exists():
            config_file = working_directory / f"{host_name}.ini"
        elif Path(f"ngbackup.ini").exists():
            config_file = working_directory / "ngbackup.ini"  
        
        if not config_file:
            self.logger.log(logging.CRITICAL, "No valid configuration file found")
            sys.exit(-1)

        self.logger.log(logging.INFO, "Reading configuration file %s", config_file.as_posix())            

        self.__config.read(config_file.as_posix())

        self.logger.log(logging.INFO, "Completed reading configuratin file")              
        
    def __init_intervals(self):
        link_intervals: dict[str, str] = {}
        for k,v in self.__config.items("link_intervals"):
            link_intervals[k] = v

        for k,v in self.__config.items("intervals"):
            self.logger.log(logging.DEBUG, f"K: {k} V: {v}")
            values = list(v.split())
            duration = 0
            rotations = 0
            link = ''
            if len(values) < 2:
                self.logger.log(logging.ERROR, f"Missing values for {k}. Skipping...")
            else:
                duration = values[0]
                rotations = values[1]
                link = None
                if link_intervals.get(k):
                    link = self.intervals.get(link_intervals.get(k), None)                    
                interval = Interval(k, duration, rotations, self.default_inc_name_template, link)
                self.intervals[k] = interval
                    
    def __init_inc_name_templates(self):
        if self.__config["defaults"]["inc_name_template"]:
            self.default_inc_name_template = self.__config["defaults"]["inc_name_template"]

        for k,v in self.__config.items("inc_name_template"):
            interval = self.intervals.get(k)
            if interval:
                interval.inc_name_template = v.strip('"')

    def __read_defaults(self):
        if self.__config["defaults"]["ssh_key"]:
            self.default_ssh_key = NgUtil.make_path(self.__config["defaults"]["ssh_key"].strip('"'))
        
        if sys.platform == 'win32':
            cygwin_home = self.__config["defaults"]["cygwin_home"].strip('"')
            if cygwin_home and Path(cygwin_home).exists():
                self.logger.log(logging.DEBUG, "Cygwin Home found. Checking for rsync and ssh")
                ssh_path = Path(cygwin_home) / "bin" / "ssh.exe"
                if not ssh_path.exists():
                    self.logger.log(logging.DEBUG, "SSH not found at %s. Install ssh package.", ssh_path.as_posix())
                    sys.exit(-1)
                else:
                    self.ssh_bin = ssh_path
                rsync_path = Path(cygwin_home) / "bin" / "rsync.exe"
                if not rsync_path.exists():
                    self.logger.log(logging.DEBUG, "Rsync not found at %s. Install rsync package.", ssh_path.as_posix())
                    sys.exit(-1)                  
                else:
                    self.rsync_bin = rsync_path

    def __init_host_keys(self):
        for k,v in self.__config.items('host_key'):
            self.host_key[k] = Path(v.strip('"'))

    def __init_sync_tasks(self):
        for k,v in self.__config.items('tasks'):
            self.logger.log(logging.DEBUG, "Processing Tasks K: %s V: %s", k, v.strip('"'))
            values = list(v.split())
            src = ''
            dest = ''
            rsync_options = ''
            if len(values) >= 2:
                src = values[0].strip('"')
                dest = values[1].strip('"')
                if len(values) == 3:
                    rsync_options = values[2].strip('"')
            task: NgTask = NgTask(k, src, dest, rsync_options)
            if task.src_host:
                task.src_key = self.host_key.get(task.src_host, self.default_ssh_key)
            elif task.dest_host:
                task.dest_key = self.host_key.get(task.dest_host, self.default_ssh_key)
            
            if sys.platform == 'win32':
                task.ssh_bin = self.ssh_bin
                task.rsync_bin = self.rsync_bin
            else:
                task.ssh_bin = Path("/usr/bin/ssh")
                task.rsync_bin = Path("/usr/bin/rsync")

            self.rsync_tasks[k] = task

    def __init_notification_emails(self):
        for k,v in self.__config.items("notification_emails"):
            self.notification_emails[k] = v.strip('"')

    def __init_task_emails(self):
        expr = re.compile("(?P<label>[A-Za-z0-9]+)[(\[](?P<intervals>.*)[)\]]")
        for k,v in self.__config.items("task_emails"):
            key = k
            value = v
            self.logger.log(logging.DEBUG, "Label: %s Values: %s", k, v)
            values =  list(v.strip('"').split())
            for value in values:
                match = expr.match(value)
                label = ''
                intervals = []
                if match:
                    label = match.groupdict()["label"]
                    intervals = list(match.groupdict()["intervals"].split(','))
                else:
                    label = values[0]
                    intervals = list(self.intervals.keys())
                
                task = self.rsync_tasks.get(key, None)
                email = self.notification_emails.get(label, None)
                if task and email:
                    task.notifications[email] = intervals
                    
                        