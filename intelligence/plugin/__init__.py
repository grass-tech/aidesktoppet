import json
import random

import io
import sys
import time
from urllib.parse import unquote, urlparse
import pathlib
import json
import ctypes
import requests
import dashscope

def draw_picture_by_qwen(prompts):
    """画画工具"""
    rsp = dashscope.ImageSynthesis.call(model='wanx2.1-t2i-turbo', prompt=prompts, n=1, size='1024*1024')
    filepath = 'ERROR'
    for result in rsp.output.results:
        file_name = pathlib.PurePosixPath(unquote(urlparse(result.url).path)).parts[-1]
        filepath = f'./logs/picture/{file_name}'
        with open(filepath, 'wb+') as f:
            f.write(requests.get(result.url).content)
            f.close()
    return json.dumps({'filepath': filepath})

def find_file(filename):
    drives = []
    exits_path = []
    bitmask = ctypes.cdll.kernel32.GetLogicalDrives()
    for letter in range(65, 91):
        if bitmask & 1:
            drives.append(chr(letter) + ':\\')
        bitmask >>= 1
    if len(drives) > 1:
        for drive in drives:
            if drive == 'C:\\':
                continue
            else:
                for file_path in pathlib.Path(drive).rglob(filename):
                    exits_path.append(str(file_path))
        return json.dumps({'status': 'success', 'result': exits_path})
    else:
        return json.dumps({'status': 'failure', 'result': '无权限访问'})

def picture_understand(description, image_path):
    conversation = {'role': 'user', 'content': [{'image': f'file://{image_path}'}, {'text': description}]}
    completion = dashscope.MultiModalConversation().call(api_key=dashscope.api_key, model='qwen-vl-max', messages=[conversation])
    msg = completion['output']['choices'][0]['message'].content[0]['text']
    return msg

def get_current_time():
    """
    当你想获取时间时非常有用
    """
    return f'当前时间：{time.strftime('%Y-%m-%d %H:%M:%S')}'

def run_python_code(source_code: str):
    """
    当你想运行Python源代码时非常有用
    """
    captured_output = io.StringIO()
    original_stdout = sys.stdout
    try:
        sys.stdout = captured_output
        exec(source_code)
        output = captured_output.getvalue()
    finally:
        sys.stdout = original_stdout
    return output


remain_times = 4
number_bomb = None


def game_number_bomb(user_input_number: int | None = None):
    """
    当你需要玩数字炸弹游戏时非常有用

    :Author: Made by 0xff
    """
    global remain_times, number_bomb
    if user_input_number is None:
        number_bomb = random.randint(0, 100)
        return json.dumps(
            {'error': None,
             'number_bomb': number_bomb,
             'message': '（初始化，无信息）',
             'remain_times': remain_times,
             'operate': '你需要问用户输入一个即不大于100的数字也不小于0的数字'
             })
    else:
        if user_input_number > 100 or user_input_number < 0:
            return json.dumps(
                {'error': '数字无效',
                 'message': '数字过大或过小',
                 'number_bomb': number_bomb,
                 'remain_times': remain_times,
                 'operate': '给出信息，并要求用户再输入一个数字'
                 })
        if remain_times - 1 <= 0:
            remain_times = 4
            number_bomb = None
            return json.dumps(
                {'error': None,
                 'message': '很遗憾，你输了',
                 'number_bomb': number_bomb,
                 'operate': '给出信息，并给出玩家炸弹数字的多少'
                 })

        if user_input_number > number_bomb:
            remain_times -= 1
            return json.dumps(
                {'error': None,
                 'message': '大了',
                 'remain_times': remain_times,
                 'number_bomb': number_bomb,
                 'operate': '给出信息，并要求用户再输入一个数字'
                 })
        elif user_input_number < number_bomb:
            remain_times -= 1
            return json.dumps(
                {'error': None,
                 'message': '小了',
                 'remain_times': remain_times,
                 'number_bomb': number_bomb,
                 'operate': '给出信息，并要求用户再输入一个数字'
                 })
        else:
            return json.dumps(
                {'error': None,
                 'message': '恭喜你，猜对了',
                 'operate': '给出信息，并结束游戏'
                 })