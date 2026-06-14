from pathlib import Path
import tomllib
from types import SimpleNamespace


def _read_config(fpath):
    path = Path(__file__).resolve().parent / fpath
    if not path.exists():
        raise FileNotFoundError(f'Can not find config file "{fpath}"')
    with path.open('rb') as f:
        return tomllib.load(f)


def args_build_client():
    config = _read_config('sai_config_client.toml')
    
    return SimpleNamespace(
        root = config['paths']['root'],
        folder_sai = config['paths']['folder_sai'],
        fpath_phrases = config['paths']['fpath_phrases'],
        fpath_prompts = config['paths']['fpath_prompts'],
        folder_client = config['paths']['folder_client'],
        folder_server = config['paths']['folder_server'],

        interval = config['runtime']['interval'],
        model_default = config['runtime']['model_default'],
        repeat_substitutions = config['runtime']['repeat_substitutions'],
        image_repeat_max = config['runtime']['image_repeat_max'],
        image_repeat_parallel = config['runtime']['image_repeat_parallel'],

        tag_sai = config['tags']['tag_sai'],
        tag_sai_error = config['tags']['tag_sai_error'],
        tag_sai_working = config['tags']['tag_sai_working'],
        tag_sai_done = config['tags']['tag_sai_done'],
        tag_sai_file_start = config['tags']['tag_sai_file_start'],
        tag_sai_que = config['tags']['tag_sai_que'],
        tag_sai_ans = config['tags']['tag_sai_ans'],
        tag_sai_file_tmp = config['tags']['tag_sai_file_tmp'],

        cs_uid = config['client_server']['cs_uid'],
        cs_key = config['client_server']['cs_key'],
        cs_host = config['client_server']['cs_host'],
        cs_port = config['client_server']['cs_port'],
        name_server = config['client_server']['name_server'],
    )


def args_build_server():
    config = _read_config('sai_config_server.toml')
    
    return SimpleNamespace(
        host_inner = config.get('connection').get('host_inner'),
        port = config.get('connection').get('port'),

        history_max = config.get('workflow').get('history_max'),
        money_day_limit = config.get('workflow').get('money_day_limit'),
        
        openrouter_key = config.get('api').get('openrouter_key'),

        users = config.get('users'),
    )