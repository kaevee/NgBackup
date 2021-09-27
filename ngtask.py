from ngremote import NgRemote
from interval import Interval
from ngutil import NgUtil
from pathlib import Path, PureWindowsPath
import logging
from uriparser import UriParser
import hashlib
import os
import time
import subprocess

class NgTask:
    name: str
    src_uri: str
    src_host: str
    src_user: str
    src_path: Path
    src_key: Path

    dest_uri: str
    dest_host: str
    dest_user: str
    dest_path: Path
    dest_key: Path

    rsync_options: str
    logger: logging.Logger
    __ssh: NgRemote = None
    config: object

    ssh_bin: Path
    rsync_bin: Path

    notifications: dict[str, list] = {}
    
    def __init__(self, name: str, src: str, dest: str, rsync_options: str) -> None:
        self.name = name
        self.src_uri = src
        self.src_user, self.src_host, self.src_path = UriParser(src).values()
        self.dest_uri = dest
        self.dest_user, self.dest_host, self.dest_path = UriParser(dest).values()
        self.rsync_options = rsync_options
        self.logger = logging.getLogger(f"NgBackup.Task.{self.name}")
        self.logger.log(logging.INFO, "Initialized NgTask Name: %s UID: %s", self.name, self.uid)
    
    # region Derived Properties

    @property
    def src_remote(self) -> bool:
        if self.src_host and self.src_user:
            return True
        return False

    @property
    def dest_remote(self) -> bool:
        if self.dest_host and self.dest_user:
            return True
        return False
    
    @property
    def rsync_src_path(self) -> str:
        if self.src_path.drive:
            return NgUtil.to_cygdrive(self.src_path)
        else:
            return self.src_path.as_posix()

    @property
    def rsync_dest_path(self) -> str:
        if self.dest_path.drive:
            return NgUtil.to_cygdrive(self.dest_path)
        else:
            return self.dest_path.as_posix()

    @property
    def rsync_src_uri(self) -> str:
        if self.src_remote:
            return f"{self.src_user}@{self.src_host}:{NgUtil.normalize_path(self.src_path)}"
        else:
            return NgUtil.normalize_path(self.src_path)
    
    @property
    def rsync_dest_uri(self) -> str:
        if self.dest_remote:
            return f"{self.dest_user}@{self.dest_host}:{NgUtil.normalize_path(self.dest_path)}"
        else:
            return NgUtil.normalize_path(self.dest_path)

    @property
    def uid(self) -> str:
        str_hash = f"{self.src_uri}{self.dest_uri}{self.name}"
        hash_object = hashlib.md5(str_hash.encode())
        return hash_object.hexdigest()

    def remote_alive(self) -> bool:
        return self.__ssh.check_status()

    # endregion

    # region Platform specific backup helper methods
    def connect_remote(self):
        if self.src_remote:
            self.__ssh = NgRemote(self.src_host, 22, self.src_user, self.src_key)
        elif self.dest_remote:
            self.__ssh = NgRemote(self.dest_host, 22, self.dest_user, self.dest_key)            
        else:
            self.logger.log(logging.WARNING, "Source/Destination are not remote")

        self.__ssh.connect()
 
    def close_remote(self):
        if self.src_remote or self.dest_remote:
            self.__ssh.close()
    
    def __rotate_local_target(self, interval: Interval) -> bool:
        self.logger.log(logging.INFO, "Rotating local target for Interval: %s", interval.name)
        
        # Check if interval path exists. If not, we are running first time. 
        interval_path = self.dest_path / interval.name        
        if not interval_path.exists():
            self.logger.log(logging.DEBUG, "Interval Path: %s does no exist. Nothing to rotate", interval_path.as_posix())
            return True
        
        increment_paths = sorted(interval_path.glob('*'))
        if increment_paths and len(increment_paths) > interval.rotations:
            self.logger.log(logging.DEBUG, "Found %d increments in Interval Path: %s", len(increment_paths), interval_path.as_posix())
            count = len(increment_paths) - interval.rotations
            while count > 0:
                trim_path = increment_paths[count - 1]
                if NgUtil.rmtree(trim_path):
                    self.logger.log(logging.INFO, "Deleted %s increment %s", interval.name, trim_path)
                else:
                    self.logger.log(logging.ERROR, "Could not delete %s increment %s", interval.name, trim_path)
                    return False
                count = count - 1
        
        return True

    def __clean_local_target(self, interval: Interval):
        interval_path = self.dest_path / interval.name
        interval_path = Path(interval_path.as_posix())
        temp_increment_paths = sorted(interval_path.glob('*_temp'))
        for path in temp_increment_paths:
            if NgUtil.rmtree(path):
                self.logger.log(logging.INFO, "Deleted temp folder %s", path.as_posix())
            else:
                self.logger.log(logging.ERROR, "Could not delete temp folder %s", path.as_posix())

    def __clean_remote_target(self, interval: Interval):
        interval_path = self.dest_path / interval.name
        if not self.__ssh.exists(interval_path):
            return
        increment_paths = self.__ssh.listdir(interval_path)        
        for path in increment_paths:
            name = path.name
            if "_temp" in name:
                if self.__ssh.rmtree(path):
                    self.logger.log(logging.INFO, "Deleted temp folder %s", path.as_posix())
                else:
                    self.logger.log(logging.ERROR, "Failed to delte temp folder %s", path.as_posix())

    def __rotate_remote_target(self, interval: Interval):
        self.logger.log(logging.INFO, "Rotating remote target for Interval: %s", interval.name)

        # Check if interval path exists. If not, we are running first time. 
        interval_path = self.dest_path / interval.name
        if not self.__ssh.exists(interval_path):
            self.logger.log(logging.DEBUG, "Interval Path: %s does no exist. Nothing to rotate", interval_path.as_posix())
            return True        

        increment_paths = self.__ssh.listdir(interval_path)        
        if increment_paths and len(increment_paths) > interval.rotations:
            self.logger.log(logging.DEBUG, "Found %d increments in Interval Path: %s. Will be trimmed to: %d", len(increment_paths), interval_path.as_posix(), interval.rotations)
            count = len(increment_paths) - interval.rotations
            while count > 0:
                trim_path = increment_paths[count - 1]
                if self.__ssh.rmtree(trim_path):
                    self.logger.log(logging.INFO, "Deleted %s increment %s", interval.name, trim_path)
                else:
                    self.logger.log(logging.ERROR, "Could not delete %s increment %s", interval.name, trim_path)
                    return False
                count = count - 1

    def __prepare_local_target(self, interval: Interval, increment_name: str):
        self.logger.log(logging.INFO, "Preparing local target for Interval: %s Increment Name: %s", interval.name, increment_name)
        increment_path = self.dest_path / interval.name / increment_name
        increment_path = Path(increment_path.as_posix())
        if not increment_path.exists(): # Sanity Check. Should not exist
            try:
                increment_path.mkdir(parents=True, exist_ok=False)
                return True
            except Exception:
                self.logger.log(logging.ERROR, "Failed to create directory %s", increment_path.as_posix())
                return False
        else:
            self.logger.log(logging.ERROR, "Increment path %s exists. Contact your software vendor", increment_path.as_posix())
            return False
                
    def __prepare_remote_target(self, interval: Interval, increment_name: str):
        self.logger.log(logging.INFO, "Preparing remote target for Interval: %s Increment Name: %s", interval.name, increment_name)
        increment_path = self.dest_path / interval.name / increment_name
        if not self.__ssh.exists(increment_path):
            if self.__ssh.makedirs(increment_path):
                self.logger.log(logging.DEBUG, "Created remote directory %s", increment_path.as_posix())
                return True
            else:
                self.logger.log(logging.ERROR, "Failed to create remote directory %s", increment_path.as_posix())
                return False

    def __get_local_last_increment(self, interval: Interval) -> Path:
        interval_path = self.dest_path / f"{interval.name}"
        interval_path = Path(interval_path.as_posix())
        if not interval_path.exists():
            self.logger.log(logging.INFO, "Interval: %s path %s not found", interval.name ,interval_path.as_posix())
            return None
        increments = sorted(interval_path.glob('*'))
        if increments and len(increments) > 0:            
            return increments[len(increments) - 1]
        else:
            return None
    
    def __get_local_link_dest(self, interval: Interval) -> Path:
        self.logger.log(logging.INFO, "Finding local link dest path for %s", interval.name)
        last_increment = self.__get_local_last_increment(interval)
        if last_increment:
            return last_increment
        if interval.link:
            alt_increment = self.__get_local_last_increment(interval.link)
            if alt_increment:
                self.logger.log(logging.DEBUG, "Alternate link is being provided for Interval: %s Alternate: %s", interval.name, interval.link.name)
                return alt_increment
        return None                   

    def __get_remote_last_increment(self, interval: Interval) -> Path:
        interval_path = self.dest_path / interval.name
        if not self.__ssh.exists(interval_path):
            return None

        increments = self.__ssh.listdir(interval_path)
        if increments:
            return increments[len(increments) -1]
    
    def __get_remote_link_dest(self, interval: Interval) -> Path:
        self.logger.log(logging.INFO, "Finding remote link dest for %s", interval.name)
        last_increment = self.__get_remote_last_increment(interval)
        if last_increment:
            return last_increment
        if interval.link:
            alt_increment = self.__get_remote_last_increment(interval.link)
            if alt_increment:
                return alt_increment
        return None

    def __rename_local_target(self, src_path: Path, dest_path: Path):
        try:
            src_path.rename(dest_path)
            return True
        except Exception as exception:
            self.logger.log(logging.ERROR, "Could not rename local target %s to %s", src_path.as_posix(), dest_path.as_posix())
            return False

    def __rename_remote_target(self, src_path: Path, dest_path: Path):
        if self.__ssh.rename(src_path, dest_path):
            return True
        else:
            return False
    # endregion

    # region Control methods
    def __get_control_file_path(self, interval: Interval) -> Path:
        current_directory = Path(os.getcwd())
        control_file_path = current_directory / "control" / f"{interval.name}_{self.name}_{self.uid}"
        if not control_file_path.exists():
            try:
                fh = open(control_file_path.as_posix(), '+w')                
                fh.write(str(0))
                fh.close()
            except Exception:
                self.logger.log(logging.ERROR, "Could not create control file %s", control_file_path.as_posix())
        return control_file_path

    def __set_last_run(self, interval: Interval):
        control_file_path = self.__get_control_file_path(interval)
        timestamp = int(time.time())
        try:
            fh = open(control_file_path.as_posix(), '+w')
            fh.write(str(timestamp))
            fh.close()
        except Exception:
            self.logger.log(logging.ERROR, "Could not open control file %s for writing", control_file_path.as_posix())

    def get_last_run(self, interval: Interval) -> int:
        control_file_path: Path = self.__get_control_file_path(interval)
        if not control_file_path.exists():
            self.logger.log(logging.INFO, "Control file %s not found. Probably first run?", control_file_path.as_posix())
        str_timestamp = None
        try:
            fh = open(control_file_path, 'r')
            str_timestamp = fh.readline().strip('\n')
            fh.close
        except Exception:
            self.logger.log(logging.ERROR, "Could not read the contorl file %s", control_file_path.as_posix())
            str_timestamp = '0'
        
        try:
            return int(str_timestamp)
        except Exception:
            self.logger.log(logging.ERROR, "Could not convert timestamp %s to integer", str_timestamp)
            
    # endregion
    
    # region Backup helper methods
    def __clean_target(self, interval: Interval):
        if self.dest_remote:
            self.__clean_remote_target(interval)
        else:
            self.__clean_local_target(interval)

    def __prepare_target(self, interval: Interval, increment_name: str):
        if self.dest_remote:
            self.__prepare_remote_target(interval, increment_name)
        else:
            self.__prepare_local_target(interval, increment_name)

    def __rotate_target(self, interval: Interval):
        if self.dest_remote:
            self.__rotate_remote_target(interval)
        else:
            self.__rotate_local_target(interval)

    def __get_link_dest_path(self, interval: Interval) -> Path:
        if self.dest_remote:
            return self.__get_remote_link_dest(interval)
        else:            
            return self.__get_local_link_dest(interval)

    def __get_log_file_path(self, interval: Interval, increment_name: str):
        working_directory = Path(os.getcwd())
        log_file_path  = working_directory / "logs" / f"{self.name}_{interval.name}_{increment_name}.log"
        return log_file_path

    def __rename_target(self, src_path: Path, dest_path: Path):
        if self.dest_remote:
            return self.__rename_remote_target(src_path, dest_path)
        else:
            return self.__rename_local_target(src_path, dest_path)
    
    def build_rsync_command(self, interval: Interval, increment_name: str, temp_increment_name: str):
        cmd = f"{self.rsync_bin} -a {self.rsync_options}"            
        

        # Add ssh key if need
        if self.src_remote:
            cmd = f"{cmd} -e \"{self.ssh_bin} -i {self.src_key.as_posix()}\""
        if self.dest_remote:
            cmd = f"{cmd} -e \"{self.ssh_bin} -i {self.dest_key.as_posix()}\""
        
        # Append log-file
        log_file_path = self.__get_log_file_path(interval, increment_name)
        cmd = f"{cmd} --log-file={log_file_path.as_posix()}"

        # Append link-dest        
        link_dest_path = self.__get_link_dest_path(interval)        
        if link_dest_path:
            self.logger.log(logging.DEBUG, "Link Dest Path: %s", link_dest_path.as_posix())        
            if link_dest_path.drive:
                cmd = f"{cmd} --link-dest={NgUtil.to_cygdrive(link_dest_path)}"
            else:
                cmd = f"{cmd} --link-dest={link_dest_path.as_posix()}"

        # Append source and destination
        rsync_cmd = f"{cmd} {self.rsync_src_uri} {self.rsync_dest_uri}/{interval.name}/{temp_increment_name}"

        return rsync_cmd
    
    # endregion

    # region Backup
    def synchronize(self, interval: Interval):
        if self.src_remote or self.dest_remote:
            status = self.__ssh.check_status()
            if not status:
                return
        
        self.logger.log(logging.INFO, "Running incremental backup for Interval: %s", interval.name)        
        increment_name = interval.get_increment_name()
        increment_path = self.dest_path / interval.name / increment_name
        temp_increment_name = f"{increment_name}_temp"
        temp_increment_path = self.dest_path / interval.name / temp_increment_name
        self.__clean_target(interval)
        rsync_cmd = self.build_rsync_command(interval, increment_name, temp_increment_name)
        self.logger.log(logging.DEBUG, "Rsync Command: %s", rsync_cmd)
        self.__prepare_target(interval, temp_increment_name)
        try:
            result = subprocess.run(rsync_cmd, capture_output=True, shell=True)
            if result.returncode == 0:
                self.logger.log(logging.INFO, "Successfully completed %s backup of %s", interval.name, self.name)
                if self.__rename_target(temp_increment_path, increment_path):
                    self.logger.log(logging.DEBUG, "Successfully renamed %s to %s", temp_increment_path.as_posix(), increment_path.as_posix())
                    self.__rotate_target(interval)
                    self.__set_last_run(interval)
            else:
                self.logger.log(logging.INFO, "Failed to complete %s backup of %s", interval.name, self.name)
        except Exception as ex:
            str_out = result.stdout.decode('utf8')
            str_err = result.stdout.decode('utf8')
            self.logger.log(logging.ERROR, ex)
            self.logger.log(logging.ERROR, "Stdout: %s", str_out)
            self.logger.log(logging.ERROR, "Stderr: %s", str_err)

    # endregion