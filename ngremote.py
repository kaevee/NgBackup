from pathlib import Path
import paramiko
from paramiko import transport
from paramiko.client import AutoAddPolicy, SSHClient
from paramiko.rsakey import RSAKey
from paramiko.ssh_exception import AuthenticationException, BadHostKeyException, SSHException
import logging

class NgRemote:
    host: str
    user: str
    port: int
    private_key: RSAKey
    __ssh_client: SSHClient
    logger: logging.Logger

    def __init__(self, host: str, port: int, user: str, ssh_key_path: Path) -> None:
        self.private_key = paramiko.RSAKey.from_private_key_file(ssh_key_path.as_posix())
        self.host = host
        self.user = user
        self.port = port        
        self.__ssh_client = SSHClient()
        self.__ssh_client.set_missing_host_key_policy(AutoAddPolicy())
        self.logger = logging.getLogger(f"NgBackup.NgRemote.{self.user}_{self.host}")        

    def connect(self):
        try:
            self.__ssh_client.connect(hostname=self.host, port=self.port, username=self.user, pkey=self.private_key)            
            self.logger.log(logging.INFO, "Connected successfully")
        except AuthenticationException as ae:
            self.logger.log(logging.ERROR, "Connect: %s", ae)
        except BadHostKeyException as bh:
            self.logger.log(logging.ERROR, "Connect: %s", bh)
        except SSHException as se:
            self.logger.log(logging.ERROR, "Connect: %s", se)
        except Exception as ex:
            self.logger.log(logging.ERROR, "Connect: %s", ex)

    def close(self):
        try:
            self.__ssh_client.close()
        except Exception as ex:
            self.logger.log(logging.ERROR, "Exception raied when remote connection is closed")

    def check_status(self):
        transport = self.__ssh_client.get_transport()
        if transport and transport.is_active():
            return True
        else:
            return False

    @property
    def is_alive(self) -> bool:
        return self.check_status()

    def exists(self, path: Path) -> bool:
        transport = self.__ssh_client.get_transport()
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            sftp.stat(path.as_posix())
            return True
        except FileNotFoundError as ex:
            return False
        except Exception as ex:
            self.logger.log(logging.ERROR, "Failed to list the path %s", path.as_posix())
            return False
    
    def listdir(self, path: Path) -> list[Path]:
        transport = self.__ssh_client.get_transport()
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:            
            entries = sorted(sftp.listdir(path.as_posix()))
            increments: list[Path] = []
            for entry in entries:
                p = path / entry
                increments.insert(len(increments), p)
            return increments
        except Exception as ex:
            self.logger.log(logging.ERROR, "Exception raised while listing files at %s", path.as_posix())
            return None

    def makedirs(self, path: Path) -> bool:
        try:
            stdin, stdout, stderr = self.__ssh_client.exec_command(f"mkdir -p {path.as_posix()}")
            return True
        except Exception as Ex:
            self.logger.log(logging.ERROR, "Exception raised while creating directory %s", path.as_posix())
            return False
    
    def makedirs_old(self, path: Path) -> bool:
        transport = self.__ssh_client.get_transport()
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            sftp.mkdir(path.as_posix())
            return True
        except:
            self.logger.log(logging.ERROR, "Exception raised when creating directory %s", path.as_posix())
            return False

    def rename(self, src_path: Path, dest_path: Path):
        transport = self.__ssh_client.get_transport()
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            sftp.rename(src_path.as_posix(), dest_path.as_posix())
            return True
        except Exception as ex:
            self.logger.log(logging.ERROR, "Exception raised while renaming %s to %s", src_path.as_posix(), dest_path.as_posix())
            return False

    def rmtree(self, path: Path) -> bool:
        cmd = f"rm -rf {path.as_posix()}"
        try:
            stdin, stdout, stderr = self.__ssh_client.exec_command(cmd)
            if stderr.read().decode('utf8') == '':
                return True
            else:
                self.logger.log(logging.ERROR, stderr.read().decode('utf8'))
                return False            
        except Exception as ex:
            self.logger.log(logging.ERROR, "Failed to delete path %s", path.as_posix())
            return False