from dataclasses import dataclass, field
from math import ceil
import pandas as pd
from typing import Type

from utility_classes.video_info_utils import VideoDTO


@dataclass
class VCAContainer():
    
    videoDTO: VideoDTO
    csv_file_path: str
    dataframe: pd.DataFrame = field(init=False, repr=False)
    description_df: pd.DataFrame = field(init=False, repr=False)
    total_frames: int = field(init=False)
    
    
    def __post_init__(self):
        """
        Sets instance variable values after the `__init__` function is completed
        """
        self.dataframe: pd.DataFrame = pd.read_csv(self.csv_file_path)
        self.description_df = self.dataframe.describe()
        self.total_frames = len(self.dataframe)