from os import stat
from pathlib import Path, PureWindowsPath
from shutil import rmtree

class NgUtil:
    
    @staticmethod
    def to_cygdrive(path: Path) -> str:
        drive = path.drive[0].lower()
        parts = list(path.parts)
        parts[0] = drive
        parts.insert(0, '/cygdrive')
        return Path(*parts).as_posix()    

    @staticmethod
    def normalize_path(path: Path) -> str:
        """Returns cygwin path for paths with drive letter

        Args:
            path (Path): Path

        Returns:
            str: Path to string (with cygdrive if windows path)
        """
        tmp_path = PureWindowsPath(path.as_posix())
        if tmp_path.drive:
            return NgUtil.to_cygdrive(tmp_path)      
        else:
            return path.as_posix()

    @staticmethod
    def make_path(str_path: str) -> Path:
        try:
            return Path(str_path)
        except Exception:
            return None
    
    @staticmethod
    def rmtree(path: Path) -> bool:
        try:
            rmtree(path.as_posix())
            return True
        except Exception:
            return False