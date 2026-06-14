import aiofiles
import aiohttp
import asyncio
import base64
from datetime import datetime
from docx import Document
import json
import mimetypes
import os
import re
import socket
import subprocess
import time


from models import MODELS
from prompts import prompt_auto
from utils import args_build_client


class Client:
    def __init__(self, args):
        self.args = args
        
        self.phrases = {}
        self.prompts = {}
        
        self.phrases_last_load = 0
        self.prompts_last_load = 0

        self.session = None

        self.tasks = set()
        
        self.lock = asyncio.Lock()

    async def apply_phrases(self, content):
        async with self.lock:
            for key, value in self.phrases.items():
                content = content.replace(key, value)
        return content

    async def ask(self, text, model, prompt=None, history=None, attach=None, 
                  images=None, kind='text'):
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.args.cs_host, self.args.cs_port),
            timeout=10000.)

        sock = writer.transport.get_extra_info('socket')
        if sock is not None:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, 'TCP_KEEPIDLE'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            elif hasattr(socket, 'TCP_KEEPALIVE'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPALIVE, 60)
            if hasattr(socket, 'TCP_KEEPINTVL'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 60)
            if hasattr(socket, 'TCP_KEEPCNT'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 10)

        data = {
            'text': text,
            'model': model,
            'name': self.args.cs_uid,
            'key': self.args.cs_key,
            'restart': True,
            'kind': kind,
        }

        if attach:
            data['attach'] = attach

        if prompt:
            data['prompt'] = prompt
        
        if images:
            data['images'] = images
        
        if history:
            data['history'] = history

        json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        size_header = len(json_data).to_bytes(4, byteorder='big')
        
        writer.write(size_header)
        await writer.drain()
        
        chunk_size = 65536
        for i in range(0, len(json_data), chunk_size):
            writer.write(json_data[i:i + chunk_size])
            await writer.drain()

        resp = await asyncio.wait_for(reader.read(), timeout=10000.)

        writer.close()
        await writer.wait_closed()

        return json.loads(resp.decode('utf-8'))

    async def close(self):
        print(f'\n... closing ...')
        if self.tasks:
            for fpath in self.tasks:
                print(f'WARNING --- Task "{fpath}" is not finished')
        if self.session is not None:
            await self.session.close()

    async def expand_content(self, content, project):
        pattern = r'\[\[\[([^>]+?)(?:\s*>\s*([^\]]+))?\]\]\]'
        matches = re.findall(pattern, content)

        for match in matches:
            file_part, section = [m.strip() for m in match]
            fpath = self.get_fpath(file_part, project)
            if not fpath:
                raise ValueError(f'Can not find file "{file_part}"')

            if fpath.endswith('.doc') or fpath.endswith('.docx'):
                if section:
                    raise ValueError(f'Sections are not supported for word')
                doc = Document(fpath)
                full_content = '\n'.join([p.text for p in doc.paragraphs])
            else:
                async with aiofiles.open(fpath, 'r', encoding='utf-8') as f:
                    full_content = await f.read()
            
            if section:
                lines = full_content.split('\n')
                content_to_insert = []
                in_section = False
                section_header = '#'*2 + f' {section}'
                for line in lines:
                    if line.strip() == section_header:
                        in_section = True
                        continue
                    if in_section and line.startswith('#'*2 + f' '):
                        break
                    if in_section:
                        content_to_insert.append(line)
                content_file = '\n'.join(content_to_insert).strip()
                if not content_file:
                    msg = f'Section "{section}" not found in "{file_part}"'
                    raise ValueError(msg)
            else:
                content_file = full_content.strip()
            
            replacement = '['*3 + f'{file_part}'
            if section:
                replacement += f' > {section}'
            replacement += ']'*3
            
            content = content.replace(replacement, content_file)

        return content

    async def finalize(self, fpath, content, tail, answer, n, cost, t, label):
        content = self.content_to_answer(content, answer, n, cost, t)
        async with aiofiles.open(fpath, 'w', encoding='utf-8') as f:
            await f.write(content + tail)
        self.notify('SAI', f'{label} ({cost:.4f}$, {t:.1f}s)')
        async with self.lock:
            self.tasks.remove(fpath)

    async def load_phrases(self):
        t = time.time()
        s = '>' * 3
        fpath = self.args.fpath_phrases
        
        if not os.path.exists(fpath):
            raise FileNotFoundError('Can not find file with phrases')
        
        if os.path.getmtime(fpath) <= self.phrases_last_load:
            return
        
        async with self.lock:
            self.phrases = {}
            
            async with aiofiles.open(fpath, 'r', encoding='utf-8') as f:
                content = await f.read()

                for line in content.split('\n'):
                    if s in line:
                        key, value = line.split(f' {s} ', 1)
                        self.phrases[key.strip()] = value.strip()
            
            self.phrases_last_load = t
    
    async def load_projects(self):
        for project in os.listdir(self.args.root):
            folder = os.path.join(self.args.root, project, self.args.folder_sai)
            if not os.path.isdir(folder):
                continue
            for fname in os.listdir(folder):
                if not fname.endswith('.md'):
                    continue
                fpath = os.path.join(folder, fname)
                async with self.lock:
                    if fpath not in self.tasks:
                        self.tasks.add(fpath)
                        asyncio.create_task(self.process(fpath, project))

    async def load_prompts(self):
        t = time.time()
        s = '#' * 2 + ' ' + '='*3 + ' '
        fpath = self.args.fpath_prompts
        
        if not os.path.exists(fpath):
            raise FileNotFoundError('Can not find file with prompts')
        
        if os.path.getmtime(fpath) <= self.prompts_last_load:
            return

        async with self.lock:
            self.prompts = {}
            
            async with aiofiles.open(fpath, 'r', encoding='utf-8') as f:
                content = await f.read()

                p = None
                for line in content.split('\n'):
                    if line.startswith(s):
                        p = line.split(s)[1].strip()
                        self.prompts[p] = []
                    elif p:
                        self.prompts[p].append(line)
            
            for p in self.prompts:
                self.prompts[p] = '\n'.join(self.prompts[p]).strip()
            
            self.prompts_last_load = t

    async def process(self, fpath, project):
        fname = os.path.basename(fpath).split('.')[0]

        async def err(content, msg):
            text = f'{self.args.tag_sai_error} [{str(msg)}]'
            content = content.replace(self.args.tag_sai, text)
            content = content.replace(self.args.tag_sai_working, text)
            content += tail
            async with aiofiles.open(fpath, 'w', encoding='utf-8') as f:
                await f.write(content)
            self.notify('SAI Error', f'{fname}: {msg}', is_error=True)
            async with self.lock:
                self.tasks.remove(fpath)

        async with aiofiles.open(fpath, 'r+', encoding='utf-8') as f:
            full_content = await f.read()

        if self.args.tag_sai not in full_content:
            async with self.lock:
                self.tasks.remove(fpath)
            return

        parts = full_content.split(self.args.tag_sai, 1)
        prefix = parts[0]
        tail = parts[1] if len(parts) > 1 else ''
        s = '#' * 2 + ' ' + self.args.tag_sai_file_tmp
        if s.lower() in tail.lower():
            tail = f'\n\n\n{s}' + tail.split(s)[-1].split(s.lower())[-1]
        else:
            tail = ''
        content = prefix + self.args.tag_sai

        try:
            content, model, kind = self.content_find_model(content)
        except Exception as e:
            return await err(content, e)

        try:
            content, options, option_names = self.content_find_options(content)
        except Exception as e:
            return await err(content, e)

        try:
            content, attach, attach_names = self.content_find_attach(content, project)
            content, images, image_names = self.content_find_images(content, project)
            attach_name = attach_names + image_names
        except Exception as e:
            return await err(content, e)
        
        try:
            content, prompt, prompt_name = self.content_find_prompt(content)
        except Exception as e:
            return await err(content, e)
        
        content = self.content_to_structured(content,
            model, prompt_name, attach_name, option_names)

        async with aiofiles.open(fpath, 'w', encoding='utf-8') as f:
            await f.write(content + tail)

        try:
            for _ in range(self.args.repeat_substitutions):
                prompt = await self.expand_content(prompt, project)
        except Exception as e:
            return await err(content, e)

        prompt = await self.apply_phrases(prompt)

        request = content.split(self.args.tag_sai)[0].strip()

        try:
            for _ in range(self.args.repeat_substitutions):
                request = await self.expand_content(request, project)
        except Exception as e:
            return await err(content, e)

        request = await self.apply_phrases(request)

        try:
            text, history = self.build_messages(request)
        except Exception as e:
            return await err(content, e)

        content = content.replace(self.args.tag_sai, self.args.tag_sai_working)
        
        async with aiofiles.open(fpath, 'w', encoding='utf-8') as f:
            await f.write(content + tail)

        t = time.perf_counter()

        image_count = options.get('image_count', 1)

        if kind != 'image' and image_count != 1:
            return await err(content, 'image-count is supported only for image models')

        if kind == 'image' and image_count > 1:
            sem = asyncio.Semaphore(self.args.image_repeat_parallel)

            async def one_request():
                async with sem:
                    return await self.ask(
                        text=text,
                        model=model,
                        prompt=prompt,
                        history=history,
                        attach=attach,
                        images=images,
                        kind=kind,
                    )

            results = await asyncio.gather(
                *(one_request() for _ in range(image_count))
            )
        else:
            results = [
                await self.ask(
                    text=text,
                    model=model,
                    prompt=prompt,
                    history=history,
                    attach=attach,
                    images=images,
                    kind=kind,
                )
            ]
                
        results_ok = [r for r in results if 'error' not in r]
        results_err = [r for r in results if 'error' in r]

        if len(results_ok) == 0:
            msg = '; '.join(str(r['error']) for r in results_err) or 'unknown error'
            return await err(content, msg)

        cost = sum(r.get('cost', 0.) for r in results_ok)
        n = len(history or []) // 2 + 1

        if kind == 'image':
            all_images = []
            text_parts = []

            if len(results_err) > 0:
                text_parts.append(
                    f'_⚠️ Не удалось сгенерировать '
                    f'{len(results_err)} из {len(results)} вариантов._'
                )
                
            for i, res in enumerate(results_ok, 1):
                if res.get('response'):
                    txt = self.check_answer(res['response'])
                    if image_count > 1:
                        text_parts.append(f'**Вариант {i}.**\n\n{txt}')
                    else:
                        text_parts.append(txt)

                all_images.extend(res.get('images') or [])

            if all_images:
                try:
                    saved = await self.save_images(
                        all_images,
                        fpath,
                        prefix=options.get('image_prefix', ''),
                    )
                except Exception as e:
                    return await err(content, e)

                image_md = '\n'.join(
                    f'![{os.path.basename(p)}]({os.path.basename(p)})'
                    for p in saved
                )

                if text_parts:
                    answer = '\n\n'.join(text_parts) + '\n\n' + image_md
                else:
                    answer = image_md

            elif text_parts:
                answer = '\n\n'.join(text_parts)

            else:
                return await err(content, f'Пустой/странный ответ ({results})')

        else:
            res = results_ok[0]

            if res.get('response'):
                answer = self.check_answer(res['response'])
            else:
                return await err(content, f'Пустой/странный ответ ({res})')

        t = time.perf_counter() - t

        return await self.finalize(
            fpath,
            content,
            tail,
            answer,
            n,
            cost,
            t,
            fname,
        )

    async def run(self):
        self.session = aiohttp.ClientSession()
        try:
            while True:
                await self.load_phrases()
                await self.load_prompts()
                await self.load_projects()
                await asyncio.sleep(self.args.interval)
        finally:
            await self.close()

    async def save_images(self, images, fpath, prefix=''):
        folder = os.path.dirname(fpath)

        stamp = datetime.now().strftime('%d-%m-%Y:%H-%M-%S-%f')[:-3]

        prefix = self.safe_filename_part(prefix)
        if prefix:
            stem = f'{prefix}-{stamp}'
        else:
            stem = stamp

        saved = []

        for uri in images:
            m = re.match(r'data:([^;]+);base64,(.*)', uri, re.DOTALL)
            if not m:
                raise ValueError('Bad image data from server')

            mime, b64 = m.group(1), m.group(2)

            ext = mime.split('/')[-1].lower()
            if ext == 'jpeg':
                ext = 'jpg'

            data = base64.b64decode(b64)
            out_path = await self.write_unique_file(folder, stem, ext, data)

            saved.append(out_path)

        return saved

    async def write_unique_file(self, folder, stem, ext, data):
        for i in range(1, 10000):
            suffix = '' if i == 1 else f'-{i:02d}'
            fname = f'{stem}{suffix}.{ext}'
            fpath = os.path.join(folder, fname)

            try:
                async with aiofiles.open(fpath, 'xb') as f:
                    await f.write(data)
                return fpath
            except FileExistsError:
                continue

        raise ValueError('Can not create unique filename')

    def build_messages(self, content):
        if not content.endswith('\n'):
            content += '\n'

        h2 = '#' * 2
        tag_que = re.escape(self.args.tag_sai_que)
        tag_ans = re.escape(self.args.tag_sai_ans)
        pattern = re.compile(
            rf'{re.escape(h2)}\s*({tag_que}|{tag_ans})-(\d+)(?:.*\n)*?\n((?:.|\n)*?)(?=\n{re.escape(h2)}\s*(?:{tag_que}|{tag_ans})-\d+|\Z)',
            re.MULTILINE
        )

        messages = []
        isq = False
            
        for match in pattern.finditer(content):
            kind, num, block_content = match.groups()
            is_question = kind.lower() == self.args.tag_sai_que.lower()
            if isq and is_question:
                raise ValueError('No or invalid question')
            if not isq and not is_question:
                raise ValueError('No or invalid question')
            isq = is_question
            messages.append({
                'role': 'user' if isq else 'assistant',
                'content': block_content.strip()
            })
        
        if not isq:
            raise ValueError('No or invalid question')

        text = messages[-1]['content']
        history = messages[:-1] if len(messages) > 1 else None
        
        return text, history

    def check_answer(self, answer):
        h1 = '#'
        h2 = '#' * 2
        
        for key, value in self.phrases.items():
            answer = answer.replace(key, f'{key[0]}!!!!!{key[1:]}')
        
        answer = answer.replace(
            f'{h1} {self.args.tag_sai_file_start}',
            f'{h1} !!!!! {self.args.tag_sai_file_start}'
        )

        answer = answer.replace(
            f'{h2} {self.args.tag_sai_que}-',
            f'{h2} !!!!! {self.args.tag_sai_que} !!!!! -'
        )

        answer = answer.replace(
            f'{h2} {self.args.tag_sai_ans}-',
            f'{h2} !!!!! {self.args.tag_sai_ans} !!!!! -'
        )

        answer = answer.replace(
            self.args.tag_sai,
            '!!!!!здесь был тег сая!!!!!'
        )

        return answer
    
    def content_current_question_start(self, content):
        q = '#' * 2 + ' ' + self.args.tag_sai_que
        matches = list(re.finditer(r'(?m)^' + re.escape(q) + r'-\d+', content))
        if not matches:
            return 0
        return matches[-1].start()

    def content_find_attach(self, content, project):
        has_answer = self.content_has_answer(content)
        current_start = self.content_current_question_start(content)

        attachments = []
        names = []

        def add_name(raw):
            if raw not in names:
                names.append(raw)

        def repl(m):
            raw = m.group(1).strip()

            if not raw.lower().endswith('.pdf'):
                return m.group(0)

            add_name(raw)

            # TODO: fix this
            # should_upload = (not has_answer) or (m.start() >= current_start)
            should_upload = True

            if not should_upload:
                return ''

            fpath = self.get_fpath(raw, project)
            if not fpath:
                raise ValueError(f'Can not find file "{raw}"')

            with open(fpath, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')

            attachments.append({
                'filename': os.path.basename(fpath),
                'data': f'data:application/pdf;base64,{b64}',
            })

            return ''

        content = re.sub(r'\{\{\{\s*([^}]+?)\s*\}\}\}', repl, content)

        return content, attachments, names

    def content_find_images(self, content, project):
        IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp', '.gif')

        has_answer = self.content_has_answer(content)
        current_start = self.content_current_question_start(content)

        images = []
        names = []

        def add_name(raw):
            if raw not in names:
                names.append(raw)

        def repl(m):
            raw = m.group(1).strip()

            if not raw.lower().endswith(IMAGE_EXTS):
                return m.group(0)

            add_name(raw)

            should_upload = (not has_answer) or (m.start() >= current_start)

            if not should_upload:
                return ''

            fpath = self.get_fpath(raw, project)
            if not fpath:
                raise ValueError(f'Can not find file "{raw}"')

            mime, _ = mimetypes.guess_type(fpath)
            mime = mime or 'image/png'

            with open(fpath, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')

            images.append(f'data:{mime};base64,{b64}')

            return ''

        content = re.sub(r'\{\{\{\s*([^}]+?)\s*\}\}\}', repl, content)

        return content, images, names

    def content_find_model(self, content):
        pattern = '>' * 3 + r'\s*([^\s{]+)'
        match = re.search(pattern, content)
        
        if not match:
            model = self.args.model_default
        else:
            model = match.group(1).strip()
        if model in MODELS:
            entry = MODELS[model]
        else:
            items = [m for m in MODELS.values() if m['name_full'] == model]
            if len(items) != 1:
                raise ValueError(f'Unknown model "{model}"')
            entry = items[0]

        kind = entry.get('kind', 'text')
        model_full = entry['name_full']

        if match:
            content = content.replace(match.group(0), '', 1)
        
        return content, model_full, kind

    def content_find_options(self, content):
        options = {
            'image_count': 1,
            'image_prefix': '',
        }

        option_names = []

        pattern = re.compile(
            r'(?m)^\s*' + '%'*3 + r'\s*([A-Za-z0-9_-]+)\s*:?\s*(.*?)\s*$'
        )

        def repl(m):
            key = m.group(1).strip().lower().replace('_', '-')
            value = m.group(2).strip()

            if key in ('image-count', 'image-n', 'images', 'variants'):
                try:
                    n = int(value)
                except Exception:
                    raise ValueError(f'Bad image-count value "{value}"')

                if n < 1 or n > self.args.image_repeat_max:
                    raise ValueError(
                        f'image-count must be from 1 to {self.args.image_repeat_max}'
                    )

                options['image_count'] = n

            elif key in ('image-prefix', 'prefix'):
                value = value.strip().strip('"').strip("'")
                options['image_prefix'] = value

            else:
                raise ValueError(f'Unknown SAI option "{key}"')

            option_names.append(m.group(0).strip())

            return ''

        content = pattern.sub(repl, content)

        return content, options, option_names

    def content_find_prompt(self, content):
        prompt = []
        prompt_names = []
        for name in re.findall('=' * 3 + r' (.+)', content):
            if name not in self.prompts:
                raise ValueError(f'Unknown prompt "{name}"')
            if self.args.tag_sai_que not in content:
                content = content.replace(f'=== {name}', '')
            prompt_content = self.prompts[name]
            if '---Автоматический промпт---' in prompt_content:
                prompt_content = prompt_auto(name)
            prompt.append(prompt_content)
            prompt_names.append('='*3 + f' {name}')
        return content, '\n\n'.join(prompt), '\n'.join(prompt_names)

    def content_has_answer(self, content):
        s = '#' * 2 + ' ' + self.args.tag_sai_ans
        return bool(re.search(r'(?m)^' + re.escape(s) + r'-\d+', content))

    def content_to_answer(self, content, answer, number, cost, t):
        h2 = '#' * 2

        content = content.replace(self.args.tag_sai_working, '').strip() + '\n\n\n'
        content += f'{h2} {self.args.tag_sai_ans}-{number} [{cost:-7.4f}$; {t:-5.2f} sec]'
        content += '\n\n' + answer + '\n\n\n'
        content += f'{h2} {self.args.tag_sai_que}-{number + 1}' + '\n\n\n'
        content += '\n\n\n' + self.args.tag_sai_done

        return content

    def content_to_structured(self, content, model=None,
                              prompt=None, attach=None, options=None):
        header_parts = [f'# {self.args.tag_sai_file_start} ']
        if model:
            header_parts.append('>'*3 + f' {model}')
        if attach:
            items = attach if isinstance(attach, (list, tuple)) else [attach]
            for a in items:
                header_parts.append('\n' + '{'*3 + a + '}'*3)
        if options:
            items = options if isinstance(options, (list, tuple)) else [options]
            for o in items:
                header_parts.append('\n' + o)
        if prompt:
            header_parts.append(f'\n{prompt}')
        
        header = ''.join(header_parts) + '\n\n\n'

        q = '#'*2 + ' ' + self.args.tag_sai_que
        if q in content:
            idx = content.find(q)
            content = header + content[idx:]
        else:
            content = content.replace(self.args.tag_sai, '').strip()
            content = header + f'{q}-1\n\n{content}\n\n\n{self.args.tag_sai}'
        
        return content

    def get_fpath(self, file_part, project):
        fpath = os.path.expanduser(os.path.join('~/Downloads', file_part))
        if os.path.isfile(fpath):
            return fpath

        fpath = os.path.join(self.args.root, project, file_part)
        if os.path.isfile(fpath):
            return fpath

        fpath = os.path.join(self.args.root, file_part)
        if os.path.isfile(fpath):
            return fpath

    def notify(self, title, message, is_error=False):
        # TODO: добавить поддержку разных ОС (сейчас работает только в OsX)
        sound = 'Sosumi' if is_error else 'Glass'
        message = message.replace('\\', '\\\\').replace('"', '\\"')
        title = title.replace('\\', '\\\\').replace('"', '\\"')
        try:
            subprocess.Popen([
                'osascript', '-e',
                f'display notification "{message}" with title "{title}" sound name "{sound}"'
            ])
        except Exception:
            pass

    def safe_filename_part(self, text, max_len=60):
        text = text.strip()
        text = re.sub(r'[^\w\-\.]+', '-', text, flags=re.UNICODE)
        text = text.strip('-_.')
        if len(text) > max_len:
            text = text[:max_len].strip('-_.')
        return text


if __name__ == '__main__':
    client = Client(args_build_client())
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        pass