import os
from pathlib import Path
import pandas as pd
from datetime import datetime
from codecarbon import track_emissions

from gaia.utils.ffmpeg import create_ffmpeg_encoding_command, prepare_sliced_videos
from gaia.utils.config import EncodingConfig, get_output_directory, Rendition

from gaia.utils.timing import IdleTimeEnergyMeasurement

from gaia.utils.dataframe import get_dataframe_from_csv

from gaia.utils.ntfy import send_ntfy

from gaia.hardware.intel import intel_rapl_workaround

from gaia.utils.benchmark import BenchmarkParser

from gaia.hardware.nvidia_top import NvidiaTop

CLI_PARSER = BenchmarkParser()

NTFY_TOPIC: str = 'aws_encoding'


ENCODING_CONFIG_PATHS: list[str] = [
    # 'config_files/encoding_test_1.yaml',
    # 'config_files/encoding_test_2.yaml',
    # 'config_files/default_encoding_config.yaml',
    # 'config_files/test_encoding_config.yaml',
    '../config_files/mmsys_encoding_h264.yaml',
    # 'config_files/encoding_config_h264.yaml',
    # 'config_files/encoding_config_h265.yaml'
]

INPUT_FILE_DIR: str = '../data'
SLICE_FILE_DIR: str = 'slice'
RESULT_ROOT: str = 'results'
COUNTRY_ISO_CODE: str = 'AUT'

USE_SLICED_VIDEOS: bool = CLI_PARSER.is_sliced_encoding()
DRY_RUN: bool = CLI_PARSER.is_dry_run()  # if True, no encoding will be executed
USE_CUDA: bool = CLI_PARSER.is_cuda_enabled()
INCLUDE_CODE_CARBON: bool = CLI_PARSER.is_code_carbon_enabled()

def prepare_data_directories(
    encoding_config: EncodingConfig, 
    result_root: str = RESULT_ROOT, 
    video_names: list[str] = list()
) -> list[str]:
    '''Used to generate all directories that are used for the video encoding

    Args:
        encoding_config (EncodingConfig): config class that contains the values that are required to generate the directories.
        result_root (str, optional): _description_. Defaults to RESULT_ROOT.
        video_names (list[str], optional): _description_. Defaults to list().

    Returns:
        list[str]: returns a list of all directories that were created
    '''
    data_directories = encoding_config.get_all_result_directories(video_names)
    
    tmp: list[str] = list()
    for duration in encoding_config.segment_duration:
        for directory in data_directories:
            if directory.count(f'{duration}s') == 2:
                tmp.append(directory)
                
    data_directories = tmp

    for directory in data_directories:
        directory_path: str = f'{result_root}/{directory}'
        Path(directory_path).mkdir(parents=True, exist_ok=True)
    return data_directories


def get_video_input_files(video_dir: str, encoding_config: EncodingConfig) -> list[str]:
    
    def is_file_in_config(file_name: str) -> bool:
        if encoding_config.encode_all_videos: 
            return True
        
        file = file_name.split('.')[0]
        if USE_SLICED_VIDEOS:
            file = file.split('_')[0]
        return file in encoding_config.videos_to_encode
    
    input_files: list[str] = [file_name for file_name in os.listdir(
        video_dir) if is_file_in_config(file_name)]

    if len(input_files) == 0:
        raise ValueError('no video files to encode')

    return input_files

@track_emissions(
    # offline=True,
    # country_iso_code='AUT',
    measure_power_secs=1,
    output_dir=RESULT_ROOT,
    save_to_file=True,
)
def execute_ffmpeg_encoding(
        cmd: str,
        video_name: str,
        codec: str,
        preset: str,
        rendition: Rendition,
        duration: int
) -> None:
    global nvidia_top, metric_results

    if USE_CUDA:
        # executes the cmd with nvidia monitoring
        result_df = nvidia_top.get_resource_metric_as_dataframe(cmd)
        
        result_df[['preset', 'codec', 'duration']] = preset, codec, duration
        result_df[['bitrate', 'width', 'height']] = rendition.bitrate, rendition.width, rendition.height
        result_df['video_name'] = video_name
        
        metric_results.append(result_df)
        
    elif DRY_RUN:
        print(cmd)
    else:
        os.system(cmd)

def write_encoding_results_to_csv():
    global nvidia_top, metric_results
    
    current_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    result_path = f'{RESULT_ROOT}/encoding_results_{current_time}.csv'
    if INCLUDE_CODE_CARBON:
        emission_df = get_dataframe_from_csv(f'{RESULT_ROOT}/emissions.csv')
        # merge codecarbon and timing_df results

        if USE_CUDA:
            nvitop_df = NvidiaTop.merge_resource_metric_dfs(metric_results, exclude_timestamps=True)
            merged_df = pd.concat([emission_df, nvitop_df], axis=1)
            # save to disk
            merged_df.to_csv(result_path)
            os.system(f'rm {RESULT_ROOT}/emissions.csv')

def get_filtered_sliced_videos(encoding_config: EncodingConfig, input_dir: str) -> list[str]:
    input_files: list[str] = get_video_input_files(
        input_dir, encoding_config)

    if not USE_SLICED_VIDEOS:
        return input_files

    ret_input_files: list[str] = list()

    for duration in encoding_config.segment_duration:
        for file in input_files:
            if f'_{duration}s_' in file:
                ret_input_files.append(file)

    return sorted(ret_input_files)

def execute_encoding_benchmark():
    
    send_ntfy(NTFY_TOPIC, 'start sequential encoding process')
    input_dir = SLICE_FILE_DIR if USE_SLICED_VIDEOS else INPUT_FILE_DIR

    for en_idx, encoding_config in enumerate(encoding_configs):
        
        send_ntfy(NTFY_TOPIC, f'start encoding_config - ({en_idx + 1}/{len(encoding_configs)})')

        input_files = get_filtered_sliced_videos(encoding_config, input_dir)[:2]
        print(input_files)

        # encode for each duration defined in the config file
        for idx, duration in enumerate(encoding_config.segment_duration):
            duration_input_files = [file for file in input_files if f'_{duration}s_' in file] if USE_SLICED_VIDEOS else input_files
            prepare_data_directories(encoding_config, video_names=duration_input_files)
            
            send_ntfy(NTFY_TOPIC, f'start duration {duration}s - ({idx + 1}/{len(encoding_config.segment_duration)})')

            # encode each video found in the input files corresponding to the duration
            for video in duration_input_files:
                for codec in encoding_config.codecs:
                    for preset in encoding_config.presets:
                        for rendition in encoding_config.renditions:

                            output_dir: str = f'{RESULT_ROOT}/{get_output_directory(codec, video, duration, preset, rendition)}'
                            use_dash_format: bool = USE_SLICED_VIDEOS == False
                            
                            cmd = create_ffmpeg_encoding_command(
                                f'{input_dir}/{video}', 
                                output_dir, rendition, preset, duration, codec, 
                                use_dash=use_dash_format, 
                                pretty_print=DRY_RUN,
                                cuda_enabled=USE_CUDA,
                                quiet_mode=CLI_PARSER.is_quiet_ffmpeg()
                                ) if not DRY_RUN else 'sleep 0.1'
                            
                            execute_ffmpeg_encoding(
                                    cmd, video, codec, preset, rendition, duration)
                                
    write_encoding_results_to_csv()
    
    


if __name__ == '__main__':
    try:
        send_ntfy(NTFY_TOPIC, 
              f'''start benchmark 
              - CUDA: {USE_CUDA} 
              - SLICE: {USE_SLICED_VIDEOS}
              - DRY_RUN: {DRY_RUN}
              - saving results in {RESULT_ROOT}
              ''', print_message=True)
        Path(RESULT_ROOT).mkdir(parents=True, exist_ok=True)

        intel_rapl_workaround()
        IdleTimeEnergyMeasurement.measure_idle_energy_consumption(result_path=f'{RESULT_ROOT}/encoding_idle_time.csv', idle_time_in_seconds=1)  

        encoding_configs: list[EncodingConfig] = [EncodingConfig.from_file(
            file_path) for file_path in ENCODING_CONFIG_PATHS]
        print(len(encoding_configs))
        if USE_SLICED_VIDEOS:
            send_ntfy(NTFY_TOPIC, f'slicing videos')
            print('aaaaaaa')
            prepare_sliced_videos(encoding_configs, INPUT_FILE_DIR, SLICE_FILE_DIR, DRY_RUN)
            send_ntfy(NTFY_TOPIC, f'finished slicing videos')

        if USE_CUDA:
            nvidia_top = NvidiaTop()
            metric_results: list[pd.DataFrame] = list()

        # execute_encoding_benchmark()
    except Exception as err:
        send_ntfy(NTFY_TOPIC, f'Something went wrong during the benchmark, Exception: {err}', print_message=True)

    finally:
        send_ntfy(NTFY_TOPIC, 'finished benchmark', print_message=True)

