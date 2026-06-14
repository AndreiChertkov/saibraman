from datetime import datetime
from docx import Document
import os
import zoneinfo


def prompt_auto(name):
    return {
        'cv': prompt_cv,
        'location': prompt_location,
        'projects': prompt_projects,
    }[name]()


def prompt_cv():
    root = os.path.dirname(os.path.abspath(__file__))
    root = os.path.join(root, '../', '../', '../')
    fold = os.path.join(root, 'identity', 'резюме')
    
    subfolders = [
        f for f in os.listdir(fold) if os.path.isdir(os.path.join(fold, f))]
    
    dated_folders = []
    for folder in subfolders:
        if len(folder) == 7 and folder[4] == '-':
            if folder[:4].isdigit() and folder[5:].isdigit():
                try:
                    date_obj = datetime.strptime(folder, '%Y-%m')
                    dated_folders.append((date_obj, folder))
                except ValueError:
                    continue
    
    dated_folders.sort(key=lambda x: x[0], reverse=True)
    latest_date, latest_folder = dated_folders[0]

    fpath = os.path.join(fold, latest_folder, 'Резюме_Андрей_Чертков.docx')
    
    doc = Document(fpath)

    text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])

    text = 'Ниже я привожу моё актуальное резюме на русском языке:\n\n' + text
    
    return text


def prompt_location():
    months_ru = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'}

    days_of_week = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье']

    zone = zoneinfo.ZoneInfo('Europe/Moscow')
    now = datetime.now(zone)

    day = now.day
    month = months_ru[now.month]
    year = now.year
    time_str = now.strftime('%H:%M')
    day_of_week = days_of_week[now.weekday()]

    text = ''
    text += f'Сегодня {day} {month} {year} года; '
    text += f'день недели - {day_of_week}; '
    text += f'время около {time_str}. '
    text += f'Я нахожусь в России, в городе Москва. '

    return text


def prompt_projects():
    dsc, ins = _collect_projects()

    text = ''
    text += '\n\nПривожу последовательно описания всех проектов (каждый из проектов начинается заголовком первого уровня, содержащим имя проекта на английском языке; обрати внимание, что описание некоторых проектов может быть совершенно пустым, тогда имеется только заголовок первого уровня с именем проекта и всё):\n\n'
    text += '\n\n\n'.join(dsc)

    text += '\n\nПривожу последовательно описания всех инструкций из всех проектов (каждая из инструкций начинается заголовком первого уровня, содержащим имя инструкции на русском языке):\n\n'
    text += '\n\n\n'.join(ins)

    return text


def _collect_projects():
    root = os.path.dirname(os.path.abspath(__file__))
    root = os.path.join(root, '../', '../', '../')

    dsc = []
    ins = []

    projects = []
    for project in os.listdir(root):
        folder = os.path.join(root, project)
        if os.path.isdir(folder) and project[0] not in ['.', '_', '$', '@']:
            projects.append(project)
    projects.sort()

    for project in projects:
        folder = os.path.join(root, project)
        if not os.path.isdir(folder):
            continue
        
        fpath = os.path.join(folder, '_.md')
        if os.path.exists(fpath):
            with open(fpath, 'r', encoding='utf-8') as f:
                dsc.append(f.read())
        else:
            print(f'WARNING: нет описания проекта "{project}"')
        
        folder = os.path.join(folder, '_ins')
        if not os.path.isdir(folder):
            continue

        for fname in os.listdir(folder):
            if not fname.endswith('.md') or fname[0] == '_':
                continue
            
            fpath = os.path.join(folder, fname)
            with open(fpath, 'r', encoding='utf-8') as f:
                ins.append(f.read())
    
    return dsc, ins