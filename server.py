import base64
from datetime import datetime
import json
import os
import requests
import socket
import threading
import zoneinfo


from utils import args_build_server


def build_messages(request, user):
    messages = []

    prompt = request.get('prompt')
    if not prompt:
        prompt = build_prompt(user)

    if prompt:
        messages.append({'role': 'system', 'content': prompt})
    
    history = request.get('history')
    if history is None:
        history = user['history']
    for item in history:
        messages.append(item)

    inp = request['text']
    attachments = request.get('attach') or []
    images = request.get('images') or []

    if images or attachments:
        content = [{'type': 'text', 'text': inp}]

        for uri in images:
            content.append({
                'type': 'image_url',
                'image_url': {'url': uri}
            })

        for a in attachments:
            content.append({
                'type': 'file',
                'file': {
                    'filename': a['filename'],
                    'file_data': a['data']
                }
            })

        plugins = [{'id': 'file-parser'}] if attachments else []
    else:
        content = inp
        plugins = []

    messages.append({'role': 'user', 'content': content})

    return messages, plugins


def build_prompt(user):
    name = user['name']
    fpath = os.path.join('server_prompts', f'{name}.txt')
    if not os.path.isfile(fpath):
        return ''
    with open(fpath, 'r', encoding='utf-8') as f:
        return f.read().strip()


def get_cost(k_inp, k_out, model, provider):
    resp = requests.get('https://openrouter.ai/api/v1/models')
    resp = resp.json()['data']
    c_inp = -1
    c_out = -1
    for item in resp:
        if item['id'] == model:
            c_inp = float(item['pricing'].get('prompt', 0))
            c_out = float(item['pricing'].get('completion', 0))
    return (int(k_inp) * c_inp + int(k_out) * c_out)


def get_date(with_date=True, with_time=True):
    zone = zoneinfo.ZoneInfo('Europe/Moscow')
    date = datetime.now(zone)

    if with_date and with_time:
        return date.strftime('%Y-%m-%d %H:%M:%S')
    elif with_date:
        return date.strftime('%Y-%m-%d')
    elif with_time:
        return date.strftime('%H:%M:%S')
    else:
        return ''


def get_money(key):
    url = 'https://openrouter.ai/api/v1/auth/key'
    headers = {'Authorization': f'Bearer {key}'}
    resp = requests.get(url, headers=headers)
    
    if resp.status_code != 200:
        msg = f'Что-то пошло не так: {resp.status_code} - {resp.text}'
        raise ValueError(msg)
        
    data = resp.json().get('data', {})
    key_limit = data.get('limit')
    key_usage = data.get('usage', 0)
    
    if key_limit is not None:
        return key_limit - key_usage
    else:
        return get_money_account(key)


def get_money_account(key):
    url = 'https://openrouter.ai/api/v1/credits'
    headers = {'Authorization': f'Bearer {key}'}
    resp = requests.get(url, headers=headers)
    resp = resp.json()['data']
    return resp['total_credits'] - resp['total_usage']


def get_request(sock, buffer_size=4096):
    size_header = sock.recv(4)
    if not size_header or len(size_header) != 4:
        raise ValueError('Не удалось прочитать заголовок размера')

    data_size = int.from_bytes(size_header, byteorder='big')

    sock.settimeout(300.)

    data = b''
    while len(data) < data_size:
        chunk = sock.recv(min(buffer_size, data_size - len(data)))
        if not chunk:
            raise ValueError('Соединение разорвано до получения всех данных')
        data += chunk
    
    return json.loads(data.decode('utf-8'))


def init():
    info = {
        'money_start': -1,
        'day_money_start': None
    }

    users = {}
    for name, item in args.users.items():
        users[name] = {
            'name': name,
            'key': item['key'],
            'models': item.get('models', 'ANY'),
            'disable_prompt_change': item.get('disable_prompt_change', False),
            'disable_history_change': item.get('disable_history_change', False),
            'requests': 0,
            'history': []
        }
    return info, users


def init_money():
    info['money_start'] = get_money(args.openrouter_key)
    info['day_money_start'] = get_date(with_time=False)
    log_sys(f'Текущий баланс: {info["money_start"]:-.2f} $')


def log(name, model, number, cost, inp='', out='', prompt='', restart=False,
        with_user_history=False, with_file=False):
    class Wrapper:
        def wrap(self, text):
            return [text]
    wrapper = Wrapper()

    head = f'REQUEST # {number}'
    head += ' {' + f'{cost:-.4f}' + ' $}'
    head += f' [{model.split("/")[-1][:28]}]'
    if restart:
        head += ' << RE'
    if with_user_history:
        head += ' << HY'

    text = '=' * (14 + len(head)) + '\n'
    text += f'[{get_date(with_date=False)}] >> {head}'
    text += '\n' + '-' * 13 + ' ' + '-' * len(head) + '\n'
    
    if prompt:
        text += '\n'.join(wrapper.wrap('PROMPT >>> ' + prompt.strip())) + '\n\n'
    
    if inp:
        if with_file:
            inp += ' [[++ and also the attached file ++]]'
        text += '\n'.join(wrapper.wrap('INPUT  >>> ' + inp.strip())) + '\n\n'
    
    if out:
        text += '\n'.join(wrapper.wrap('OUTPUT >>> ' + out.strip())) + '\n\n'

    text += '-' * (13 + len(head)) + '\n\n'
    
    fdir = f'server_logs/{name}'
    fpath = f'log_{get_date(with_time=False)}.txt'
    
    os.makedirs(fdir, exist_ok=True)

    with open(f'{fdir}/{fpath}', 'a+', encoding='utf-8') as f:
        f.write(text + '\n')


def log_sys(text):
    text = f'[{get_date()}] >> {text}'

    fdir = 'server_logs/sys'
    fpath = f'log_{get_date(with_time=False)}.txt'
    
    os.makedirs(fdir, exist_ok=True)

    print(text)
    
    with open(f'{fdir}/{fpath}', 'a+', encoding='utf-8') as f:
        f.write(text + '\n')


def run():
    log_sys(f'Начало работы')

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host_inner, args.port))
    server.listen(5)
    server.settimeout(1.0)
    log_sys(f'Сервер успешно запущен (порт {args.port})')

    clients = []

    try:
        while True:
            try:
                sock, addr = server.accept()
            except socket.timeout:
                continue
            log_sys(f'Попытка подключения: {addr[0]}:{addr[1]}')
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

            if hasattr(socket, 'TCP_KEEPIDLE'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            elif hasattr(socket, 'TCP_KEEPALIVE'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPALIVE, 60)
            if hasattr(socket, 'TCP_KEEPINTVL'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 60)
            if hasattr(socket, 'TCP_KEEPCNT'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 10)

            clients = [c for c in clients if c.is_alive()]
            client = threading.Thread(
                target=run_request, args=(sock,), daemon=True)
            client.start()
            clients.append(client)
    
    except KeyboardInterrupt:
        log_sys('Сервер остановлен нажатием Ctrl+C')
    
    finally:
        server.close()
        alive = [c for c in clients if c.is_alive()]
        if alive:
            log_sys(f'Ожидание завершения {len(alive)} запрос(ов)...')
            for c in alive:
                c.join(timeout=1)
            still_alive = [c for c in alive if c.is_alive()]
            if still_alive:
                log_sys(f'{len(still_alive)} запрос(ов) не завершились')
        log_sys('Сервер завершил работу')


def run_request(sock):
    def res(msg, ann=None, cost=0., money=-1, images=None):
        data = {'response': msg, 'ann': ann, 'cost': cost,
            'money': money, 'images': images}
        resp = json.dumps(data, ensure_ascii=False)
        sock.sendall(resp.encode('utf-8'))
        sock.close()

    def err(msg):
        log_sys(f'ERROR : {msg}')
        try:
            resp = json.dumps({'error': msg}, ensure_ascii=False)
            sock.sendall(resp.encode('utf-8'))
            sock.close()
        except Exception as e:
            msg = f'FATAL : не могу отправить ответ ({str(e)})'
            log_sys(msg)
            try:
                sock.close()
            except Exception as e:
                msg = f'FATAL : не могу закрыть соединение ({str(e)})'
                log_sys(msg)

    try:
        day = get_date(with_time=False)
        if info['money_start'] < 0 or day != info['day_money_start']:
            init_money()

        money = get_money(args.openrouter_key)
        
        if info['money_start'] - money >= args.money_day_limit:
            msg = f'Потрачено слишком много денег за день (осталось всего {money}$). Сервер нужно перезапустить вручную для продолжения работы.'
            return err(msg)

        request = get_request(sock)

        # Ожидаемые поля в запросе:
        # name        - имя пользователя 
        #               (args.cs_uid / args.users.USER)
        # key         - уникальный ключ пользователя для подключения к серверу
        #               (args.cs_key / args.users.USER.key)
        # model       - полное имя модели из openrouter
        # text        - текст запроса
        # kind        - тип запроса: 'text' или 'image' или 'video'
        # prompt      - опциональный промпт
        # attach      - опциональное вложение (прочитанные pdf файлы)
        # images      - опциональный список графических изображений
        # history     - опциональная история предыдущих запросов
        # restart     - флаг, если True, то история на сервере стирается

        name = request.get('name')
        user = users.get(name)

        if user is None:
            return err('Неправильное имя пользователя')
        
        if request.get('key', '') != user['key']:
            return err('Неправильный секретный ключ пользователя')

        if not request.get('model'):
            return err('Не задана нейросетевая модель')
        elif user['models'] == 'ANY':
            pass
        elif request['model'] not in user['models']:
            return err('Задана недоступная нейросетевая модель')

        if len(request.get('text', '')) < 2:
            return err('Некорректный запрос к модели')

        if user.get('disable_prompt_change') and request.get('prompt'):
            return err('Тебе нельзя менять системный промпт :)')

        if user.get('disable_history_change') and request.get('history'):
            return err('Тебе нельзя менять историю :)')

        if request.get('restart'):
            user['history'] = []

        log_sys(f'Подключился {name}')

        if len(user['history']) >= args.history_max * 2:
            log_sys('WARNING : запрос отклонен из-за превышения лимита истории')
            out = 'Слишком долго общаемся. Голова болит. Перезапусти меня.'
            return res(out)

        messages, plugins = build_messages(request, user)

        payload = {
            'model': request['model'],
            'messages': messages,
            'plugins': plugins,
        }

        # TODO: check
        if request.get('kind') == 'image':
            payload['modalities'] = ['image', 'text']
        payload['reasoning'] = {'enabled': True,
            'exclude': True, 'effort': 'high'}
        
        resp = requests.post('https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {args.openrouter_key}',
                'Content-Type': 'application/json'
            },
            json=payload)

        if resp.status_code != 200:
            return err(f'Ошибка API: {resp.text}')
        resp = resp.json()

        try:
            message = resp['choices'][0]['message']
            out = message.get('content')
            ann = message.get('annotations')
            raw_images = message.get('images') or []
        except Exception as e:
            return err(f'Модель ответила что-то странное (ошибка: {str(e)}; ответ целиком: {resp})')

        out_images = []
        for im in raw_images:
            if isinstance(im, str):
                out_images.append(im)
            else:
                try:
                    out_images.append(im['image_url']['url'])
                except (KeyError, TypeError):
                    pass

        if not out and not out_images:
            return err(f'Модель вернула пустой ответ (ответ целиком: {resp})')

        user['history'].append({'role': 'user', 'content': request['text']})
        
        if ann:
            user['history'].append(
                {'role': 'assistant', 'content': out, 'annotations': ann})
        else:
            user['history'].append(
                {'role': 'assistant', 'content': out or ''})
        
        user['requests'] += 1

        cost = get_cost(
            k_inp=resp['usage'].get('prompt_tokens', 0),
            k_out=resp['usage'].get('completion_tokens', 0),
            model=request['model'],
            provider=resp['provider'])

        log(name, request['model'], user['requests'], cost,
            request['text'], out, request.get('prompt'), request.get('restart'),
            with_user_history = request.get('history') is not None,
            with_file=ann is not None)
        
        msg = f'Запрос {name} (# {user["requests"]}) обработан ({cost:-.4f} $)'
        log_sys(msg)

        return res(out, ann, cost, money, out_images or None)
        
    except Exception as e:
        return err(f'Ошибка на стороне сервера ({str(e)})')


if __name__ == '__main__':
    args = args_build_server()
    info, users = init()
    run()