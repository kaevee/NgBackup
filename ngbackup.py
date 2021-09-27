import time
from ngconfig import NgConfig
from pathlib import Path
import logging
import logging.handlers
import os
import sys

class NgBackup:

    logger: logging.Logger
    config: NgConfig
    
    def __init__(self) -> None:        
        self.setup_folders()
        self.setup_logging()
        self.config = NgConfig()

    def setup_logging(self):
        self.logger = logging.getLogger('NgBackup')
        self.logger.setLevel(logging.DEBUG)

        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Create directory if need
        log_dir: Path = Path(os.getcwd()) / "logs"

        # Setup the log file
        log_file = log_dir / "ngbackup.log"
        fh = logging.handlers.RotatingFileHandler(log_file.as_posix(), maxBytes=1048576)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        # Setup console log
        if sys.stdout.isatty:
            ch = logging.StreamHandler()
            ch.setLevel(logging.DEBUG)
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)

        self.logger.log(logging.INFO, "Logging Initialized")        

    def setup_folders(self):
        working_directory = Path(os.getcwd())
        
        log_directory = working_directory / "logs"
        if not log_directory.exists():
            log_directory.mkdir()

        control_directory = working_directory / "control"
        if not control_directory.exists():
            control_directory.mkdir()
    
    def run(self):
        for taskname in self.config.rsync_tasks.keys():
            task = self.config.rsync_tasks.get(taskname)
            if task.src_remote or task.dest_remote:
                task.connect_remote()
                if not task.remote_alive():
                    continue
            for interval_name in self.config.intervals.keys():
                interval = self.config.intervals.get(interval_name)
                last_run = task.get_last_run(interval)
                current_time = int(time.time())
                self.logger.log(logging.INFO, "Task: %s, Last Run: %d", task.name, last_run)
                if (current_time - last_run) > interval.duration:
                    task.synchronize(interval)
            if task.src_remote or task.dest_remote:
                task.close_remote()

    @staticmethod
    def to_cygdrive(path: Path) -> str:
        drive = path.drive[0].lower()
        parts = list(path.parts)
        parts[0] = drive
        parts.insert(0, '/cygdrive')
        return Path(*parts).as_posix()
