import os

from pathlib import Path
from datetime import datetime

import pandas as pd
from codecarbon import track_emissions
from websockets import InvalidState

from greem.utility.ffmpeg import create_sequential_encoding_cmd
from greem.utility.configuration_classes import EncodingConfig, EncodingConfigDTO

from greem.utility.timing import IdleTimeEnergyMeasurement
from greem.utility.dataframe import get_dataframe_from_csv

from greem.hardware.intel import intel_rapl_workaround
from greem.monitoring.nvidia_top import NvidiaTop

from greem.utility.cli_parser import CLI_PARSER

NTFY_TOPIC: str = "aws_encoding"


ENCODING_CONFIG_PATHS: list[str] = [
    # "config_files/segment_encoding_h264.yaml",
    # "config_files/segment_encoding_h265.yaml",
    "config_files/test_encoding_config.yaml"
]

INPUT_FILE_DIR: str = "../dataset/ref_265"
RESULT_ROOT: str = "results"
COUNTRY_ISO_CODE: str = "AUT"

USE_SLICED_VIDEOS: bool = CLI_PARSER.is_sliced_encoding()
# if True, no encoding will be executed
DRY_RUN: bool = CLI_PARSER.is_dry_run()
USE_CUDA: bool = CLI_PARSER.is_cuda_enabled()
INCLUDE_CODE_CARBON: bool = CLI_PARSER.is_code_carbon_enabled()

metric_results: list[pd.DataFrame] = []

nvidia_top = NvidiaTop() if USE_CUDA else None


"""
def encoding(input_ffmpeg: str,
             output_file: str,
             codec: str,
             encoding_preset: str,
             bitrate: str,
             width: str,
             height: str
             ) -> str:
    output_file_name: str = build_output_file_name(
        output_file, codec, encoding_preset, bitrate, width, height)

    result_file_path: str = f'{RESULT_PATH}/{codec}/enc/{output_file_name}.{codec}'

    lib_params: str = ' -x264-params' if '264' in codec else ' -x265-params'

    command = f'ffmpeg {FFMPEG_QUIET} -y {FFMPEG_CUDA} -i {input_ffmpeg}'\
        f' -probesize 10M -vcodec {get_codec_lib(codec)}'\
        f'{lib_params} "log-level=error --keyint {IFRAME_INTERVAL*FPS} --min-keyint {IFRAME_INTERVAL*FPS} --no-scenecut" -preset {encoding_preset}' \
        f' -b:v {bitrate}k -minrate {bitrate}k -maxrate {bitrate}k -bufsize {3*int(bitrate)}k' \
        f' {result_file_path}'

    os.system(command)
    return result_file_path

"""


# def create_ffmpeg_encoding_command(
#     input_file_path: str,
#     output_dir: str,
#     rendition: Rendition,
#     preset: str,
#     segment_duration: int,
#     codec: str,
#     framerate: int = 0,
#     constant_rate_factor: int = -1,
#     cuda_enabled: bool = False,
#     quiet_mode: bool = False,
# ) -> str:
#     """Creates the ffmpeg command for encoding a video file

#         command = f'ffmpeg {FFMPEG_QUIET} -y {FFMPEG_CUDA} -i {input_ffmpeg}'\
#         f' -probesize 10M -vcodec {get_codec_lib(codec)}'\
#         f'{lib_params} "log-level=error --keyint {IFRAME_INTERVAL*FPS} --min-keyint {IFRAME_INTERVAL*FPS} --no-scenecut" -preset {encoding_preset}' \
#         f' -b:v {bitrate}k -minrate {bitrate}k -maxrate {bitrate}k -bufsize {3*int(bitrate)}k' \
#         f' {result_file_path}'
#         """
#     cmd: list[str] = ["ffmpeg -y"]
#     if cuda_enabled:
#         cmd.append(CUDA_ENC_FLAG)
#     if quiet_mode:
#         cmd.append(QUIET_FLAG)

#     cmd.append(f"-re -i {input_file_path}")

#     if constant_rate_factor > -1:
#         cmd.append(f"-crf {constant_rate_factor}")

#     fps_str: str = ""
#     if framerate > 0:
#         fps_str = str(framerate)  # type: ignore

#     cmd.extend(get_representation_ffmpeg_flags(
#         [rendition], preset, codec, fps=fps_str))

#     fps: int = (
#         ceil(VideoInfo(input_file_path).get_fps())
#         if framerate is None or framerate == 0
#         else framerate
#     )
#     keyframe: int = fps * segment_duration

#     cmd.extend(
#         [
#             f"-keyint_min {keyframe}",
#             f"-g {keyframe}",
#         ]
#     )

#     cmd.extend([f"{output_dir}/output.mp4"])

#     join_string: str = " \n" if DRY_RUN else " "

#     lib_params: str = " -x264-params" if "264" in codec else " -x265-params"

#     command = (
#         f"ffmpeg {QUIET_FLAG} -y {CUDA_ENC_FLAG} -i {input_file_path}"
#         f" -probesize 10M -vcodec {get_lib_codec(codec)}"
#         f'{lib_params} "log-level=error --keyint {keyframe} --min-keyint {keyframe} --no-scenecut" -preset {preset}'
#         f" -b:v {rendition.bitrate}k -minrate {rendition.bitrate}k -maxrate {rendition.bitrate}k -bufsize {3*int(rendition.bitrate)}k"
#         f" {output_dir}/encoding_output.mp4"
#     )

#     return command
# return join_string.join(cmd)


"""
def scaling(
        input_ffmpeg: str, 
        output_file: str, 
        codec: str, 
        encoding_preset: str, 
        bitrate: str,
        width: str, 
        height: str
        ):
    output_file_name = build_output_file_name(
        output_file, codec, encoding_preset, bitrate, width, height)

    result_file_path: str = f'{RESULT_PATH}/{codec}/enc/{output_file_name}_scaled.{codec}'

    command = f'ffmpeg {FFMPEG_QUIET} -y {FFMPEG_CUDA} -i {input_ffmpeg} '\
        f'-vf scale={width}:{height} ' \
        f'{result_file_path}'

    os.system(command)
    return result_file_path"""


# def create_ffmpeg_scaling_command(
#     output_dir: str,
#     rendition: Rendition,
#     cuda_enabled: bool = False,
#     quiet_mode: bool = False,
# ) -> str:
#     cmd: list[str] = ["ffmpeg -y"]
#     if cuda_enabled:
#         cmd.append(CUDA_ENC_FLAG)
#     if quiet_mode:
#         cmd.append(QUIET_FLAG)

#     cmd.append(f"-re -i {output_dir}/encoding_output.mp4")

#     cmd.extend(
#         [
#             f"-vf scale={rendition.get_resolution_dir_representation()}",
#             f"{output_dir}/scaling_output.mp4",
#         ]
#     )

#     # command = f'ffmpeg {QUIET_FLAG} -y {CUDA_ENC_FLAG} -i {input_file_path} '\
#     #     f'-vf scale={rendition.width}:{rendition.height} ' \
#     #     f'{output_dir}/output.mp4'

#     join_string: str = " \n" if DRY_RUN else " "

#     # return command
#     return join_string.join(cmd)


# def get_representation_ffmpeg_flags(
#     renditions: list[Rendition],
#     preset: str,
#     codec: str,
#     fps: str = "",
# ) -> list[str]:
#     """Returns the ffmpeg flags for the renditions"""
#     representations: list[str] = list()

#     fps_repr: str = "" if len(fps) == 0 else f",fps={fps}"

#     for idx, rendition in enumerate(renditions):
#         bitrate = rendition.bitrate
#         height = rendition.height
#         width = rendition.width
#         representation: list[str] = [
#             f"-b:v:{idx} {bitrate}k -minrate {bitrate}k -maxrate {bitrate}k -bufsize {3*int(bitrate)}k",
#             f"-c:v:{idx} {get_lib_codec(codec)} -filter:v:{idx}",
#             f'"scale={width}:{height}',
#             f'{fps_repr}"',
#             f"-preset {preset}",
#         ]

#         representations.extend(representation)

#     return representations


def prepare_data_directories(
    encoding_config: EncodingConfig,
    result_root: str = RESULT_ROOT,
) -> list[str]:
    """Used to generate all directories that are used for the video encoding

    Args:
        encoding_config (EncodingConfig): config class that contains the values that are required to generate the directories.
        result_root (str, optional): _description_. Defaults to RESULT_ROOT.
        video_names (list[str], optional): _description_. Defaults to list().

    Returns:
        list[str]: returns a list of all directories that were created
    """
    # data_directories = encoding_config.get_all_result_directories(video_names)

    data_directories = [
        dto.get_output_directory() for dto in encoding_config.get_encoding_dtos()
    ]

    for directory in data_directories:
        directory_path: str = f"{result_root}/{directory}"
        Path(directory_path).mkdir(parents=True, exist_ok=True)

    return data_directories


def get_video_input_files(video_dir: str, encoding_config: EncodingConfig) -> list[str]:
    input_files: list[str] = [file_name for file_name in os.listdir(video_dir)]

    if len(input_files) == 0:
        raise ValueError("no video files to encode")

    return input_files


def get_filtered_sliced_videos(
    encoding_config: EncodingConfig, input_dir: str
) -> list[str]:
    input_files: list[str] = get_video_input_files(input_dir, encoding_config)

    return sorted(input_files)


def execute_encoding_benchmark(encoding_configs: list[EncodingConfig]):
    input_dir = INPUT_FILE_DIR

    for encoding_config in encoding_configs:
        input_files = sorted(
            [file for file in os.listdir(
                INPUT_FILE_DIR) if file.endswith(".265")]
        )

        # encode for each duration defined in the config file
        prepare_data_directories(encoding_config)

        encoding_dtos: list[EncodingConfigDTO] = encoding_config.get_encoding_dtos(
        )
        # encode each video found in the input files corresponding to the duration
        for video_name in input_files:
            for dto in encoding_dtos:
                # output_dir = f'{RESULT_ROOT}/{dto.get_output_directory(video_name.removesuffix(".265"))}'
                input_file_path = f"{input_dir}/{video_name}"
                encoding_cmd = (
                    create_sequential_encoding_cmd(
                        input_file_path, video_name, RESULT_ROOT, dto
                    )
                    if not DRY_RUN
                    else "sleep 0.1"
                )

                print(dto.codec)
                print(encoding_cmd)
                execute_encoding_stage(encoding_cmd, dto, video_name)
                break

                # scaling_cmd: str = create_ffmpeg_scaling_command(
                #     output_dir, dto.rendition, cuda_enabled=USE_CUDA
                # )

                # execute_encoding_cmd(cmd, dto, video_name)
                # execute_scaling_stage(scaling_cmd, dto, video_name)
            break
    # write_encoding_results_to_csv()


@track_emissions(
    offline=True,
    country_iso_code="AUT",
    log_level="error" if CLI_PARSER.is_quiet_ffmpeg() else "debug",
    measure_power_secs=1,
    output_dir=RESULT_ROOT,
    save_to_file=True,
    project_name="encoding_stage",
)  # type: ignore
def execute_encoding_stage(
    cmd: str, encoding_dto: EncodingConfigDTO, video_name: str
) -> None:
    execute_encoding_cmd(cmd, encoding_dto, video_name)


@track_emissions(
    offline=True,
    country_iso_code="AUT",
    log_level="error" if CLI_PARSER.is_quiet_ffmpeg() else "debug",
    measure_power_secs=1,
    output_dir=RESULT_ROOT,
    save_to_file=True,
    project_name="scaling_stage",
)  # type: ignore
def execute_scaling_stage(
    cmd: str, encoding_dto: EncodingConfigDTO, video_name: str
) -> None:
    execute_scaling_stage(cmd, encoding_dto, video_name)


@track_emissions(
    offline=True,
    country_iso_code="AUT",
    log_level="error" if CLI_PARSER.is_quiet_ffmpeg() else "debug",
    measure_power_secs=1,
    output_dir=RESULT_ROOT,
    save_to_file=True,
)  # type: ignore
def execute_encoding_cmd(
    cmd: str, encoding_dto: EncodingConfigDTO, video_name: str
) -> None:
    if USE_CUDA:
        # executes the cmd with nvidia monitoring
        result_df = nvidia_top.get_resource_metric_as_dataframe(cmd)

        rendition = encoding_dto.representation

        result_df[["preset", "codec", "duration"]] = (
            encoding_dto.preset,
            encoding_dto.codec,
            encoding_dto.segment_duration,
        )
        result_df[["bitrate", "width", "height"]] = (
            rendition.bitrate,
            rendition.width,
            rendition.height,
        )
        result_df["video_name"] = video_name
        result_df["output_path"] = encoding_dto.get_output_directory()

        metric_results.append(result_df)

    elif DRY_RUN:
        print(cmd)
    else:
        os.system(cmd)


def write_encoding_results_to_csv():
    current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    result_path = f"{RESULT_ROOT}/encoding_results_{current_time}.csv"
    if INCLUDE_CODE_CARBON:
        emission_df = get_dataframe_from_csv(f"{RESULT_ROOT}/emissions.csv").dropna(
            axis=1, how="all"
        )

        # merge codecarbon and timing_df results
        if USE_CUDA:
            nvitop_df = NvidiaTop.merge_resource_metric_dfs(
                metric_results, exclude_timestamps=True
            ).dropna(axis=1, how="all")
            merged_df = pd.concat([emission_df, nvitop_df], axis=1)

            # save to disk
            merged_df.to_csv(result_path)
            os.system(f"rm {RESULT_ROOT}/emissions.csv")


if __name__ == "__main__":
    try:
        Path(RESULT_ROOT).mkdir(parents=True, exist_ok=True)

        if USE_CUDA:
            nvidia_top = NvidiaTop()

        intel_rapl_workaround()
        IdleTimeEnergyMeasurement.measure_idle_energy_consumption(
            result_path=f"{RESULT_ROOT}/encoding_idle_time.csv", idle_time_in_seconds=1
        )

        encoding_configurations: list[EncodingConfig] = [
            EncodingConfig.from_file(file_path) for file_path in ENCODING_CONFIG_PATHS
        ]

        if len(encoding_configurations) == 0:
            raise InvalidState("No encoding configuration files provided")

        metric_results: list[pd.DataFrame] = []
        timing_metadata: dict[int, dict] = {}

        execute_encoding_benchmark(encoding_configurations)

    except InvalidState as err:
        print(err)

    finally:
        print("done")
