from pathlib import Path, PureWindowsPath
from ngutil import NgUtil
import re
import logging

class UriParser:
    user: str = None
    host: str = None
    path: Path = None

    logger: logging.Logger
    # TODO Refactoring the regular expression is needed
    expr = re.compile("(?P<user>\S+)@(?P<host>[A-Za-z0-9.\-]+):(?P<path>\S+)")

    def __init__(self, uri) -> None:
        logger = logging.getLogger("NgBackup.UriParser")
        match = self.expr.match(uri)
        if match:
            self.user = match.groupdict().get('user')
            self.host = match.groupdict().get('host')
            self.path = self.make_path(match.groupdict().get('path'))
        else:
            self.path = self.make_path(uri)
    
    def make_path(self, str_path: str) -> Path:
        try:
            path = PureWindowsPath(str_path)
            if path.drive:
                return path
            else:
                return Path(str_path)
        except Exception:
            self.logger.log(logging.ERROR, "Invalid path string %s", str_path)
            return None
    
    def values(self):
        values = (self.user, self.host, self.path)
        return values