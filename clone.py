import os
import subprocess


from utils import args_build_client


FILES = [
    'server.py',
    'utils.py',
    'sai_config_server.toml',
]
DIRS = [
    'server_prompts',
]


def clean_out(out):
    lines = [l for l in out.splitlines() if not l.startswith('** ')]
    return '\n'.join(lines).strip()


def copy_to_server():
    dst = f'{args.name_server}:{args.folder_server}'
    for fpath in FILES:
        src = f'{args.folder_client}/{fpath}'
        if not os.path.isfile(src):
            print(f'WARNING: нет файла {src}, пропуск')
            continue
        out = clean_out(subprocess.getoutput(f'scp {src} {dst}/'))
        if out:
            raise ValueError(f'Error copy {fpath}: {out}')
    for d in DIRS:
        src = f'{args.folder_client}/{d}'
        if not os.path.isdir(src):
            print(f'WARNING: нет папки {src}, пропуск')
            continue
        out = clean_out(subprocess.getoutput(
            f'rsync -az --delete {src}/ {dst}/{d}/'))
        if out:
            raise ValueError(f'Error sync {d}: {out}')
    print('DONE: copy to server')


def copy_from_server():
    local = f'{args.folder_client}/server_logs/'
    remote = f'{args.name_server}:{args.folder_server}/server_logs/'

    os.makedirs(local, exist_ok=True)

    cmd = f'rsync -az {remote} {local}'
    out = clean_out(subprocess.getoutput(cmd))
    if out:
        print(f'WARNING: logs sync output: {out}')

    cmd = f'ssh {args.name_server} "find {args.folder_server}/server_logs -type f -delete"'
    clean_out(subprocess.getoutput(cmd))

    print('DONE: copy from server')


def update_models():
    path = f'{args.folder_client}/models.py'
    cmd = f'conda run --no-capture-output -n sai python {path}'
    print(subprocess.getoutput(cmd))


if __name__ == '__main__':
    args = args_build_client()
    update_models()
    copy_from_server()
    copy_to_server()