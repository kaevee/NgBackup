from datetime import datetime
from pathlib import Path
class Interval:
    name: str
    duration: int
    rotations: int
    alt_link: object    
    inc_name_template: str

    def __init__(self, name: str, duration: int, rotations: int, inc_name_template: str, link: str = '') -> None:
        """Initializes the Interval object instance

        Args:
            name (str): Label of Interval
            duration (int): No of seconds beween runs
            rotations (int): No of incremental backups to keep before deleting the oldest
            inc_name_template (str): Template to generate name for increment
            link (str, optional): Alternat link-dest path. Defaults to 'self'.
        """
        self.name = name
        self.duration = int(duration)
        self.rotations = int(rotations)
        self.inc_name_template = inc_name_template
        self.link = link

    def get_increment_name(self) -> str:
        """Returns the increment using template configured in ini file

        Returns:
            str: Incremental backup directory name
        """
        return datetime.now().strftime(self.inc_name_template)
        
    def get_increment_path(self) -> Path:
        path = Path(self.name) / f"{self.get_increment_name()}"
        return path