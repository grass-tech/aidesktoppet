import sys
import time
import datetime
import random
import threading
import webbrowser

import idlelib.colorizer as colorizer
import idlelib.percolator as percolator

# 数据处理 Data Processing
import ast
import shutil
import os
import re
import struct
import json
import typing
# 音频数据处理 audio data processing
import wave
import pyaudio
import io

# 日志数据
import logs

# AI
try:
    import intelligence
    MODULE_INFO = intelligence.voice.get_module_lists()

except ImportError:
    intelligence.VoiceSwitch = False
    Client = intelligence = None
    MODULE_INFO = {}

except __import__("requests").exceptions.ConnectionError:
    intelligence.VoiceSwitch = False
    Client = None
    MODULE_INFO = {}

try:
    import runtime

except ImportError:
    runtime = None

# WindowsAPI
import ctypes
import win32gui
import win32con
import win32api

# 引入live2d库 Import Live2D
import live2d.v3 as live2d

# 界面库和OpenGL库 GUI
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog
from tkinter.scrolledtext import ScrolledText

import OpenGL.GL as GL

from PyQt5.Qt import Qt, QTimerEvent, QCursor, QThread, pyqtSignal, QRect, QFont, QTimer, \
    QIcon
from PyQt5.QtWidgets import QOpenGLWidget, QApplication, QMessageBox, QMenu, QAction, \
    QTextEdit, QPushButton

param_dict = {}
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
speech_rec = None
with open("./resources/configure.json", "r", encoding="utf-8") as f:
    def recover_backup():
        global configure
        os.remove("./resources/configure.json")
        shutil.copy2("./logs/backup/configure.json", "./resources/configure.json")
        with open("./resources/configure.json", "r", encoding="utf-8") as scf:
            configure = json.load(scf)
            scf.close()

    try:
        configure = json.load(f)
    except json.JSONDecodeError:
        f.close()
        recover_backup()
    configure_default = configure["default"]
    configure_settings = configure["settings"]
    configure_model = configure['model']

    if configure_default == "origin":
        configure_default = "vanilla"

    configure_adults = configure['model'][configure_default]['adult']
    configure_voices = configure['model'][configure_default]['voice']

    f.close()
if intelligence:
    intelligence.text.reload_memories(configure['default'])
    intelligence.ALI_API_KEY = configure_settings['cloud']['aliyun']
    intelligence.XF_API_ID = configure_settings['cloud']['xunfei']['id']
    intelligence.XF_API_KEY = configure_settings['cloud']['xunfei']['key']
    intelligence.XF_API_SECRET = configure_settings['cloud']['xunfei']['secret']


def logger(text, father_dir):
    current_file = f"{father_dir}/{time.strftime('%Y-%m-%d', time.localtime())}.txt"
    if not os.path.exists(father_dir):
        os.mkdir(father_dir)
    if not os.path.isfile(current_file):
        open(current_file, "w", encoding="utf-8").close()
    with open(f"{current_file}", "a", encoding="utf-8") as lf:
        lf.write(f"{{\n"
                 f"\t[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}] \n"
                 f" [LOGGING]: \n{text}\n"
                 f"}}\n")
        lf.close()


def parse_local_url(url: str):
    truly_url = url.format(
        ip=__import__("socket").gethostbyname(__import__("socket").gethostname()),
        year=time.strftime("%Y"),
    )
    cleaned_url = re.sub(r'\s*\+\s*', '+', truly_url)
    pattern = r'^(http|https)://([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)(:(.*?))?(/.*)?$'
    match = re.match(pattern, cleaned_url)
    if match:
        request_header = match.group(1)
        ip = match.group(2)
        port_part = match.group(4) if match.group(4) else '80'
        path = match.group(5) if match.group(5) else '/'
        try:
            port = str(eval(port_part)) if port_part else '80'
        except Exception as e:
            return None

        return f"{request_header}://{ip}:{port}{path}"


def get_audio_path(action: str):
    try:
        return (f"./resources/voice/{configure['default']}/"
                f"{get_configure_actions()[action]['play']}/"
                f"{random.choice(configure_voices[configure['model'][
                    configure_default]['action'][action]['play']])
                    if get_configure_actions()[action]['play_type'] == 'random' else
                    get_configure_actions()[action]['play_type']}")
    except (KeyError, IndexError):
        return ""


def load_template_model(model: str):
    with open("./resources/template.json", "r", encoding="utf-8") as tf:
        template = json.load(tf)
        tf.close()
    if not os.path.exists(f"./resources/voice/{model}"):
        os.mkdir(f"./resources/voice/{model}")
        for template_dir in template['voice'].keys():
            try:
                os.mkdir(f"./resources/voice/{model}/{template_dir}")
            except FileExistsError:
                pass
    for emotion_type in os.listdir(f"./resources/voice/{model}"):
        template['voice'][emotion_type] = list(map(lambda v: v.split("\\")[-1], __import__("glob").glob(
            f"./resources/voice/{model}/{emotion_type}/*.wav")))
    configure['model'].update({model: template})
    with open("./resources/configure.json", "w", encoding="utf-8") as sf:
        json.dump(configure, sf, indent=3, ensure_ascii=False)
        sf.close()


# configure
def get_configure_actions():
    return configure['model'][configure_default]['action']


# 基本功能线程 Basic Function Thread
class SpeakThread(QThread):
    """说话线程 Speak Thread"""
    information = pyqtSignal(int)

    def __init__(self, parent: QOpenGLWidget, resource_data: bytes | str):
        super().__init__(parent)
        self.parent().speaking_lists.append(True)
        self.current_speak_index = len(self.parent().speaking_lists) - 1
        self.resource_data = resource_data

    def run(self):
        if self.resource_data is None or not self.resource_data.strip():
            return
        if isinstance(self.resource_data, bytes):
            wave_source = io.BytesIO(self.resource_data)
            mode = "rb"
        else:
            wave_source = self.resource_data
            mode = "r"

        if self.parent().speaking_lists[self.current_speak_index - 1] and self.current_speak_index != 0:
            self.parent().speaking_lists[self.current_speak_index - 1] = False

        with wave.open(wave_source, mode) as wf:
            p = pyaudio.PyAudio()
            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()), channels=wf.getnchannels(),
                            rate=wf.getframerate(), output=True)
            data = wf.readframes(1024)
            while data:
                if not self.parent().speaking_lists[self.current_speak_index]:
                    break
                stream.write(data)
                data = wf.readframes(1024)
            stream.stop_stream()
            stream.close()
            p.terminate()
        self.parent().speaking_lists[self.current_speak_index] = False


class RecognitionThread(QThread):
    """语音识别线程 Speech Recognition Thread"""
    result = pyqtSignal(str)

    def __init__(self, parent: QOpenGLWidget):
        super().__init__(parent)

    def run(self):
        global speech_rec
        if configure['settings']['rec'] == "cloud":
            speech_rec = intelligence.xf_speech_recognition(
                self.result.emit,
                self.parent().recognition_failure, self.parent().recognition_closure
            )
        else:
            speech_rec = intelligence.whisper_speech_recognition(
                self.result.emit,
                self.parent().recognition_failure, self.parent().recognition_closure,
                parse_local_url(configure['settings']['local']['rec']['url'])
            )
        speech_rec.start_recognition()


class MediaUnderstandThread(QThread):
    result = pyqtSignal(tuple)

    def __init__(self, parent: QOpenGLWidget, image_path: str,
                 texts: str | None = None, is_search_online: bool = False):
        """根据媒体理解线程 Media Understand Thread"""
        super().__init__(parent)
        self.image_path = image_path
        self.is_search_online = is_search_online
        self.texts = texts

    def run(self):
        if self.texts is None:
            self.texts = random.choice(["你觉得我在干什么？", "你有什么想法呀？", "你觉得这个图片怎么样？", "请评价一下这图片"])
        try:
            answer = intelligence.text_generator(f"{self.image_path}看着这个图片{self.texts}", self.is_search_online)
        except Exception as e:
            logger(f"子应用 - 媒体文件理解 调用失败\n"
                   f"   Message: {e}", logs.HISTORY_PATH)
            self.result.emit([f"AI媒体文件理解 调用失败 AI Answer failed to call\n{type(e).__name__}: {e}",
                              f"AI媒体文件理解 调用失败 AI Answer failed to call\n{type(e).__name__}: {e}"])
            return
        logger("子应用 - AI图文理解 调用成功 Sub Application - AI Media Understand Call Success\n"
               f"   Message: {answer}", logs.HISTORY_PATH)
        self.result.emit(answer)


class TextGenerateThread(QThread):
    """文本生成器线程 Text Generation Thread"""
    result = pyqtSignal(tuple)

    def __init__(self, parent: QOpenGLWidget, text: str, is_search_online: bool = False):
        super().__init__(parent)
        self.text = text
        self.is_search_online = is_search_online

    def run(self):
        try:
            answer = intelligence.text_generator(
                self.text,
                self.is_search_online,
                url=parse_local_url(configure['settings']['local']['text']
                                    ) if configure['settings']['text']['way'] == "local" else None)
        except Exception as e:
            logger(f"子应用 - AI剧情问答 调用失败\n"
                   f"   Message: {e}", logs.HISTORY_PATH)
            self.result.emit((f"AI问答 调用失败 AI Answer failed to call\n{type(e).__name__}: {e}",
                              f"AI问答 调用失败 AI Answer failed to call\n{type(e).__name__}: {e}"))
            return
        logger(f"子应用 - AI剧情问答 调用成功\n"
               f"   Message: {answer}", logs.HISTORY_PATH)
        self.result.emit(answer)


class VoiceGenerateThread(QThread):
    """AI 文字转语音 (GSV) AI text-to-speech (GSV) module"""
    result = pyqtSignal(list)

    def __init__(self, parent: QOpenGLWidget, text: str):
        super().__init__(parent)
        self.text = text

    def run(self):
        # 数据预处理 data pre-processing
        # 排除表情等无需发音的内容 Exclude expressions such as emotion
        text = re.sub(r'(\(.*）\))', '', self.text)
        text = re.sub(r'(（.*）)', '', text)
        text = re.sub(r'(\[.*])', '', text)
        text = re.sub(r'(【.*】)', '', text)
        # 翻译和语言 Translation and language
        language = "zh"
        if configure['settings']['tts']['way'] == "local":
            if "trans" not in configure['settings']['disable']:
                if "spider" in configure_settings['translate']:
                    if "bing" in configure_settings['translate']:
                        text = intelligence.machine_translate(text)
                        language = "ja"
                elif "ai" in configure_settings['translate']:
                    if "tongyi" in configure_settings['translate']:
                        text = intelligence.tongyi_translate(text)
                        language = "ja"

            intelligence.voice_change(configure['voice_model'], MODULE_INFO)
            wav_bytes = intelligence.gsv_voice_generator(
                text, language, configure['voice_model'], MODULE_INFO,
                configure['settings']['tts']['top_k'], configure['settings']['tts']['top_p'],
                configure['settings']['tts']['temperature'], configure['settings']['tts']['speed'],
                configure['settings']['tts']['batch_size'], configure['settings']['tts']['batch_threshold'],
                parallel_infer=configure['settings']['tts']['parallel'],
                url=parse_local_url(configure['settings']['local']['gsv']))
            # 计算长度 Calculate length
            riff_header = wav_bytes[:12]
            if not riff_header.startswith(b'RIFF') or not riff_header[8:12] == b'WAVE':
                raise ValueError("Invalid RIFF/WAVE header")

            pos = 12
            fmt_chunk_data = None
            data_chunk_size = None

            # 遍历所有块直到找到fmt和data块 find fmt and data chunks
            while pos < len(wav_bytes):
                chunk_id = wav_bytes[pos:pos + 4]
                chunk_size = struct.unpack_from('<I', wav_bytes, pos + 4)[0]
                pos += 8  # 跳过chunk id和size Break past chunk id and size

                if chunk_id == b'fmt ':
                    fmt_chunk_data = wav_bytes[pos:pos + chunk_size]
                elif chunk_id == b'data':
                    data_chunk_size = chunk_size
                    break  # 找到data块后可以停止搜索 stop searching

                pos += chunk_size
                if chunk_size % 2 != 0:
                    pos += 1

            if fmt_chunk_data is None or data_chunk_size is None:
                raise ValueError("fmt or data chunk missing in WAV file")

            # 解析fmt块数据 Parse fmt chunk data
            _, channels, sample_rate, byte_rate, block_align, bits_per_sample = struct.unpack_from('<HHIIHH',
                                                                                                   fmt_chunk_data)

            # 计算音频长度（秒） Calculate audio duration
            duration = int(data_chunk_size / (sample_rate * channels * (bits_per_sample / 8)) * 1000)
        else:
            wav_bytes, duration = intelligence.ali_voice_generator(text)

        logger(f"子应用 - AI语音(GSV) 调用成功\n"
               f"   Duration {duration}\n", logs.HISTORY_PATH)
        self.result.emit([wav_bytes, duration])


# 鼠标监听器 Mouse listener
class MouseListener:
    """用于在全局鼠标穿透下进行监听 Used for global mouse penetration to listen"""
    def __init__(self):
        self.listener_thread = None
        self.isListening = False
        self.is_left_button_pressed = False
        self.is_right_button_pressed = False

    def start_listening(self):
        self.isListening = True
        self.listener_thread = threading.Thread(target=self.listen)
        self.listener_thread.start()

    def stop_listening(self):
        self.__init__()

    def listen(self):
        state_left = 0
        state_right = 0
        while self.isListening:
            current_state_left = win32api.GetKeyState(win32con.VK_LBUTTON)
            current_state_right = win32api.GetKeyState(win32con.VK_RBUTTON)
            if current_state_left != state_left:
                state_left = current_state_left
                if current_state_left < 0:
                    self.is_left_button_pressed = True
                else:
                    self.is_left_button_pressed = False
            if current_state_right != state_right:
                state_right = current_state_right
                if current_state_right < 0:
                    self.is_right_button_pressed = True
                else:
                    self.is_right_button_pressed = False
            threading.Event().wait(0.01)


class AdultEngine:
    """成人内容加载引擎 Adult content loading engine"""
    @staticmethod
    def voice() -> tuple:
        keywords = re.findall(r'\b[a-zA-Z]+\b', configure_adults['AdultDescribe'][str(configure['adult_level'])])
        keywords = ''.join(keywords)
        return keywords.lower(), configure_adults['voice'][f"Voice{keywords}"]


class ExtractFunctionDocstring(ast.NodeVisitor):
    """提取函数文档字符串 Extract function docstring"""
    def __init__(self, function_name):
        self.function_name = function_name
        self.description = None

    def visit_FunctionDef(self, node):
        if isinstance(node.parent, ast.Module) and node.name == self.function_name:
            docstring = ast.get_docstring(node)
            if docstring:
                lines = docstring.split('\n')
                if lines:
                    self.description = lines[0].strip()
        return node

    @staticmethod
    def add_parents(tree):
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node

    def extract(self, code):
        tree = ast.parse(code)
        self.add_parents(tree)
        visitor = ExtractFunctionDocstring(self.function_name)
        visitor.visit(tree)

        return visitor.description


class RemoveFunctionTransformer(ast.NodeTransformer):
    """移除函数 Remove function"""
    def __init__(self, function_name):
        self.function_name = function_name

    def visit_FunctionDef(self, node):
        if isinstance(node.parent, ast.Module) and node.name == self.function_name:
            return None
        return node

    @staticmethod
    def add_parents(tree):
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node

    def remove(self, code):
        tree = ast.parse(code)
        self.add_parents(tree)
        transformer = RemoveFunctionTransformer(self.function_name)
        new_tree = transformer.visit(tree)

        return ast.unparse(new_tree)


class Balloon:
    """
    气泡 Balloon
    """
    def __init__(self,
                 widget,
                 text: str = "",
                 fg="black",
                 bg="white",
                 justify: typing.Literal["left", "center", "right"] = "left",
                 anchor: typing.Literal["nw", "n", "ne", "w", "center", "e", "sw", "s", "se"] = "center",
                 x_offset: int = 0,
                 y_offset: int = 0,
                 show_width: int = 0,
                 follow: bool = True,
                 alpha: float = 0.95,
                 delayed=250,
                 topmost=True,
                 *args,
                 **kwargs):
        self.text = text
        self.fg = fg
        self.bg = bg
        self.width = show_width
        self.justify = justify
        self.anchor = anchor
        self.args = args
        self.kwargs = kwargs

        self.top = None
        self.id = None
        self.follow = follow
        self.widget = widget
        self.alpha = alpha
        self.delayed = delayed
        self.topmost = topmost

        self.x_offset = x_offset
        self.y_offset = y_offset

        self.widget.bind('<Enter>', lambda x: self.enter())
        self.widget.bind("<ButtonPress>", lambda x: self.leave())
        self.widget.bind('<Leave>', lambda x: self.leave())
        if self.follow:  # 跟随显示
            self.widget.bind("<Motion>", lambda x: self.move())

    def balloon_show(self):
        if self.top:
            return

        self.updata_width()

        self.top = tk.Toplevel()
        self.top.attributes("-alpha", self.alpha)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", self.topmost)
        self.top.minsize(self.width, 30)

        # 偏移量默认居中
        x = self.widget.winfo_pointerx() + self.x_offset - self.width // 2
        if self.y_offset + 15 < 15:
            self.y_offset = 0
        y = self.widget.winfo_pointery() + self.y_offset + 15
        self.top.geometry(f"+{x}+{y}")

        balloon = tk.Label(
            self.top,
            text=self.text,
            fg=self.fg,
            bg=self.bg,
            justify=self.justify,
            anchor=self.anchor,
            wraplength=self.width - 20,
            *self.args, **self.kwargs)
        balloon.pack(fill="both", expand=1, ipadx=10, ipady=5)

    def updata_width(self):
        if not self.width:
            test_long = len(self.text)
            if test_long <= 30:
                self.width = test_long * 12 + 20
            elif test_long <= 90:
                self.width = 300
            elif 90 < test_long <= 250:
                self.width = test_long + 200
            else:
                self.width = 450

    def enter(self):
        self.schedule()

    def leave(self):
        self.unschedule()
        self.destroy_balloon()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.delayed, self.balloon_show)

    def unschedule(self):
        show_id = self.id
        self.id = None
        if show_id:
            self.widget.after_cancel(show_id)

    def move(self):
        if self.top:
            x = self.widget.winfo_pointerx() + self.x_offset - self.width // 2
            if self.y_offset + 15 < 15:
                self.y_offset = 0
            y = self.widget.winfo_pointery() + self.y_offset + 15
            self.top.geometry(f"+{x}+{y}")

    def destroy_balloon(self):
        if self.top:
            self.top.destroy()
            self.top = None

    def updata_text(self, new_text, new_width=0):
        self.text = new_text
        self.width = new_width

    def unballoon(self):
        self.widget.unbind('<Enter>')
        self.widget.unbind("<ButtonPress>")
        self.widget.unbind('<Leave>')
        if self.follow:
            self.widget.unbind("<Motion>")
        try:
            del self.text
            del self.fg
            del self.bg
            del self.justify
            del self.anchor
            del self.args
            del self.kwargs

            del self.top
            del self.id
            del self.follow
            del self.widget
            del self.width
            del self.alpha
            del self.delayed
            del self.topmost

            del self.x_offset
            del self.y_offset
            return True
        except AttributeError:
            return 1


# 设置
class Setting(tk.Tk):
    def __init__(self):
        super().__init__()
        self.iconbitmap("logo.ico")
        self.title("AI-Agent  桌面宠物设置 | Desktop Pet Settings")
        self.geometry("600x460")
        self.attributes("-alpha", 0.9)
        self.attributes("-topmost", True)

        self.required_check_button_value = {}
        self.function_names = []
        self.is_selected_file = False

        self.note = ttk.Notebook(self)

        self.general_frame = tk.Frame(self)
        self.switch_frame = tk.Frame(self)
        self.intelligence_frame = tk.Frame(self)
        self.bind_frame = tk.Frame(self)
        self.character_frame = tk.Frame(self)
        self.about_frame = tk.Frame(self)
        self.note.add(self.general_frame, text="常规 General")

        tk.Label(self.general_frame, text="宠物形象 Pet Character：").place(x=5, y=5)
        clist = os.listdir("./resources/model")
        clist.append("origin")
        self.pet_character = ttk.Combobox(self.general_frame, values=clist, state="readonly")
        self.pet_character.set(configure['default'])
        self.pet_character.bind("<<ComboboxSelected>>",
                                lambda event: self.change_character(self.pet_character.get()))
        self.pet_character.place(x=200, y=5)

        self.pet_nickname_entry = ttk.Entry(self.general_frame, width=23)
        self.pet_nickname_entry.insert(0, configure['name'])
        self.pet_nickname_entry.bind("<Key>", lambda event: self.change_character(self.pet_character.get()))
        self.pet_nickname_entry.place(x=380, y=5)

        tk.Label(self.general_frame, text="翻译工具 Translation Tool：").place(x=5, y=35)
        self.translation_class = ttk.Combobox(self.general_frame, values=["爬虫 Spider", "人工智能 AI"], state="readonly")
        self.translation_class.current(0)
        if "spider" in configure_settings['translate']:
            self.translation_class.current(0)
            self.translation_tool = ttk.Combobox(self.general_frame, values=["必应 Bing"],
                                                 state="readonly")
        elif "ai" in configure_settings['translate']:
            self.translation_class.current(1)
            self.translation_tool = ttk.Combobox(self.general_frame, values=["通义千问 Tongyi"],
                                                 state="readonly")
        else:
            self.translation_tool = ttk.Combobox(self.general_frame, values=[], state="readonly")

        self.translation_class.bind("<<ComboboxSelected>>", self.change_translation_tool)
        self.translation_tool.bind("<<ComboboxSelected>>", lambda event: self.change_translate())
        self.translation_class.place(x=200, y=35)
        if "bing" in configure_settings['translate']:
            self.translation_tool.current(0)
        elif "tongyi" in configure_settings['translate']:
            self.translation_tool.current(0)
        self.translation_tool.place(x=380, y=35)

        tk.Label(self.general_frame, text="成人模式 Adult Mode: ").place(x=5, y=70)
        self.adult_lists = ttk.Combobox(self.general_frame, values=list(configure_adults['AdultDescribe'].values()),
                                        state="readonly")
        if configure['adult_level'] > 0:
            self.adult_lists.current(configure['adult_level'] - 1)
        else:
            self.adult_lists.configure(state=tk.DISABLED)
        self.adult_lists.bind(
            "<<ComboboxSelected>>",
            lambda event: self.change_configure(
                list(configure_adults['AdultDescribe'].values()).index(self.adult_lists.get()) + 1, "adult_level"))
        self.adult_lists.place(x=200, y=70)

        tk.Label(self.general_frame, text="语音模型 Voice Module：").place(x=5, y=100)
        self.voice_text_entry = ttk.Entry(self.general_frame, width=65)
        self.voice_text_entry.place(x=5, y=130)
        self.voice_model_lists = ttk.Combobox(self.general_frame, values=list(MODULE_INFO.keys()),
                                              state="readonly")
        self.voice_model_lists.set(configure['voice_model'])
        self.voice_model_lists.place(x=200, y=100)
        self.play_refer_audio = ttk.Button(self.general_frame, text="试听 Audition",
                                           command=self.play_refer_audio)
        self.play_refer_audio.place(x=380, y=100)
        self.voice_model_lists.bind("<<ComboboxSelected>>", self.change_refer_text)

        tk.Label(self.general_frame, text="水印 Watermark").place(x=5, y=180)
        self.watermark_combo = ttk.Combobox(self.general_frame, values=list(param_dict.keys()),
                                            state="readonly")
        self.watermark_combo.set(configure['watermark'].split(";")[0])
        self.watermark_combo.bind("<<ComboboxSelected>>", self.change_watermark)
        self.watermark_combo.place(x=200, y=180)

        self.watermark_scale = ttk.Scale(self.general_frame, length=200, from_=-100, to=100,
                                         command=self.change_watermark)
        self.watermark_scale.set(int(configure['watermark'].split(";")[1]))
        self.watermark_scale.place(x=380, y=180)

        self.note.add(self.switch_frame, text="开关 Switch")

        self.switches = tk.LabelFrame(self.switch_frame, text="开关列表 Switch Lists", width=590, height=100)
        self.switches.place(x=5, y=5)

        self.compatible_value = tk.BooleanVar(self)
        self.compatible_value.set(configure['settings']['compatibility'])
        self.compatible_button = ttk.Checkbutton(self.switches, text="录屏兼容 Capture Compatibility",
                                                 variable=self.compatible_value, onvalue=True, offvalue=False,
                                                 command=lambda: self.io_configure(
                                                     "{compatibility}", "settings.compatibility", bool))
        self.compatible_button.place(x=10, y=5)

        self.adult_value = tk.IntVar(self)
        self.adult_value.set(configure['adult_level'])
        self.adult_button = ttk.Checkbutton(self.switches, text="成人模式 Adult Mode",
                                            variable=self.adult_value,
                                            onvalue=1 if configure['adult_level'] == 0 else configure['adult_level'],
                                            offvalue=0,
                                            command=lambda: self.io_configure(
                                                "{adult}", "adult_level", int))
        self.adult_button.place(x=400, y=5)

        self.speech_recognition_value = tk.BooleanVar(self)
        self.speech_recognition_value.set(True if "rec" not in configure['settings']['disable'] else False)
        self.speech_recognition_button = ttk.Checkbutton(self.switches, text="语音识别 Speech Recognition",
                                                         variable=self.speech_recognition_value, onvalue=True,
                                                         offvalue=False,
                                                         command=lambda: self.io_configure("rec"))
        self.speech_recognition_button.place(x=10, y=30)

        self.ai_voice_value = tk.BooleanVar(self)
        self.ai_voice_value.set(True if "tts" not in configure['settings']['disable'] else False)
        self.ai_voice_button = ttk.Checkbutton(self.switches, text="AI语音 AI Voice",
                                               variable=self.ai_voice_value, onvalue=True, offvalue=False,
                                               command=lambda: self.io_configure("tts"))
        self.ai_voice_button.place(x=400, y=30)

        self.online_search_value = tk.BooleanVar(self)
        self.online_search_value.set(True if "online" not in configure['settings']['disable'] else False)
        self.online_search_button = ttk.Checkbutton(self.switches, text="在线搜索 Online Search",
                                                    variable=self.online_search_value, onvalue=True, offvalue=False,
                                                    command=lambda: self.io_configure("online"))
        self.online_search_button.place(x=10, y=55)

        self.translate_value = tk.BooleanVar(self)
        self.translate_value.set(True if "trans" not in configure['settings']['disable'] else False)
        self.translate_button = ttk.Checkbutton(self.switches, text="翻译 Translate",
                                                variable=self.translate_value, onvalue=True, offvalue=False,
                                                command=lambda: self.io_configure("trans"))
        self.translate_button.place(x=400, y=55)

        self.advanced_switch_frame = tk.LabelFrame(self.switch_frame,
                                                   text="高级开关 Advanced Switch", width=590, height=200)
        tk.Label(self.advanced_switch_frame, text="从\t        到\t\t 之间随机选取作为时间间隔").place(x=230, y=5)
        self.media_understand_value = tk.BooleanVar(self)
        self.media_understand_value.set(True if "media" not in configure['settings']['disable'] else False)
        self.media_understand_button = ttk.Checkbutton(self.advanced_switch_frame, text="媒体理解 Media Understand",
                                                       variable=self.media_understand_value, onvalue=True,
                                                       offvalue=False,
                                                       command=lambda: self.io_configure("media"))
        self.media_understand_minimum = ttk.Spinbox(
            self.advanced_switch_frame,
            from_=0, to=86400, width=7,
            command=lambda: self.change_configure(
                int(self.media_understand_minimum.get()), "settings.understand.min"))
        self.media_understand_minimum.set(configure['settings']['understand']['min'])
        self.media_understand_minimum.place(x=250, y=5)
        self.media_understand_maximum = ttk.Spinbox(
            self.advanced_switch_frame,
            from_=0, to=86400, width=6,
            command=lambda: self.change_configure(
                int(self.media_understand_maximum.get()), "settings.understand.max"))
        self.media_understand_maximum.set(configure['settings']['understand']['max'])
        self.media_understand_maximum.place(x=340, y=5)
        self.media_understand_button.place(x=5, y=5)

        self.globe_mouse_penetration_value = tk.BooleanVar(self)
        self.globe_mouse_penetration_value.set(True if configure['settings']['penetration']['enable'] else False)
        self.globe_mouse_penetration_button = ttk.Checkbutton(
            self.advanced_switch_frame,
            text="全局鼠标穿透 Global Mouse Penetration",
            variable=self.globe_mouse_penetration_value, onvalue=True,
            offvalue=False,
            command=lambda: self.change_configure(
                self.globe_mouse_penetration_value.get(),
                "settings.penetration.enable"
            ))
        self.globe_mouse_penetration_button.place(x=5, y=30)

        tk.Label(self.advanced_switch_frame, text="取\n消\n时\n间").place(x=50, y=55)
        self.penetration_start_value = tk.StringVar(self)
        if configure['settings']['penetration']['start']:
            self.penetration_start_value.set(configure['settings']['penetration']['start'])
        else:
            self.penetration_start_value.set("next")
        self.penetration_start_next_time = ttk.Radiobutton(
            self.advanced_switch_frame,
            text="下次启动时 When starting next time",
            variable=self.penetration_start_value,
            value="next",
            command=lambda: self.change_configure(
                self.penetration_start_value.get(),
                "settings.penetration.start"
            ))
        self.penetration_start_next_time.place(x=80, y=55)

        self.penetration_start_random = ttk.Radiobutton(
            self.advanced_switch_frame,
            text="随机 Random",
            variable=self.penetration_start_value,
            value="random",
            command=lambda: self.change_configure(
                self.penetration_start_value.get(),
                "settings.penetration.start"
            ))
        Balloon(self.penetration_start_random,
                "一旦启用就会有5 ~ 30分钟的时间无法操作。并且无法靠重启恢复！当软件关闭后会刷新计时器重新计时！\n"
                "A random time between 5 ~ 30 minutes will be disabled. You can't recover it by restarting! "
                "When the software is closed, the timer will be refreshed and restarted!",
                fg="yellow", bg="red")
        self.penetration_start_random.place(x=380, y=55)

        self.penetration_start_left_click_bottom = ttk.Radiobutton(
            self.advanced_switch_frame,
            text="左击底部 Left-click bottom",
            variable=self.penetration_start_value,
            value="left-bottom",
            command=lambda: self.change_configure(
                self.penetration_start_value.get(),
                "settings.penetration.start"
            ))
        self.penetration_start_left_click_bottom.place(x=80, y=80)

        self.penetration_start_left_click_top = ttk.Radiobutton(
            self.advanced_switch_frame,
            text="左击顶部 Left-click top",
            variable=self.penetration_start_value,
            value="left-top",
            command=lambda: self.change_configure(
                self.penetration_start_value.get(),
                "settings.penetration.start"
            ))
        self.penetration_start_left_click_top.place(x=380, y=80)

        self.penetration_start_right_click_bottom = ttk.Radiobutton(
            self.advanced_switch_frame,
            text="右击底部 Right-click bottom",
            variable=self.penetration_start_value,
            value="right-bottom",
            command=lambda: self.change_configure(
                self.penetration_start_value.get(),
                "settings.penetration.start"
            ))
        self.penetration_start_right_click_bottom.place(x=80, y=105)

        self.penetration_start_right_click_top = ttk.Radiobutton(
            self.advanced_switch_frame,
            text="右击顶部 Right-click top",
            variable=self.penetration_start_value,
            value="right-top",
            command=lambda: self.change_configure(
                self.penetration_start_value.get(),
                "settings.penetration.start"
            ))
        self.penetration_start_right_click_top.place(x=380, y=105)
        # self.penetration_want_custom = ttk.Radiobutton(
        #     self.advanced_switch_frame,
        #     text="我想什么时候 I want when",
        #     variable=self.penetration_start_value,
        #     value="want",
        #     command=lambda: self.change_configure(
        #         self.penetration_start_value.get(),
        #         "settings.penetration.start"
        #     ))
        # self.penetration_want_custom.place(x=80, y=80)

        self.advanced_switch_frame.place(x=5, y=110)

        self.note.add(self.intelligence_frame, text="人工智能 AI")

        self.intelligence_note = ttk.Notebook(self.intelligence_frame)

        self.inference_frame = tk.Frame(self.intelligence_frame)
        self.tts_parameter_frame = tk.Frame(self.intelligence_frame)
        self.intelligence_note.add(self.inference_frame, text="推理 Inference")

        self.cloud_infer = tk.LabelFrame(self.inference_frame, text="云端推理 Cloud Infer", width=590, height=150)

        tk.Label(self.cloud_infer, text="阿里云 API_KEY：").place(x=5, y=5)
        self.aliyun_apikey_entry = ttk.Entry(self.cloud_infer, width=50, show="*")
        self.aliyun_apikey_entry.insert(0, configure_settings['cloud']['aliyun'])
        self.aliyun_apikey_entry.place(x=150, y=5)

        tk.Label(self.cloud_infer, text="讯飞 API_ID：").place(x=5, y=35)
        self.xunfei_apiid_entry = ttk.Entry(self.cloud_infer, width=50, show="*")
        self.xunfei_apiid_entry.insert(0, configure_settings['cloud']['xunfei']['id'])
        self.xunfei_apiid_entry.place(x=150, y=35)

        tk.Label(self.cloud_infer, text="讯飞 API_KEY：").place(x=5, y=65)
        self.xunfei_apikey_entry = ttk.Entry(self.cloud_infer, width=50, show="*")
        self.xunfei_apikey_entry.insert(0, configure_settings['cloud']['xunfei']['key'])
        self.xunfei_apikey_entry.place(x=150, y=65)

        tk.Label(self.cloud_infer, text="讯飞 API_SECRET：").place(x=5, y=95)
        self.xunfei_apisecret_entry = ttk.Entry(self.cloud_infer, width=50, show="*")
        self.xunfei_apisecret_entry.insert(0, configure_settings['cloud']['xunfei']['secret'])
        self.xunfei_apisecret_entry.place(x=150, y=95)

        self.cloud_infer.place(x=5, y=5)

        self.local_infer = tk.LabelFrame(self.inference_frame, text="本地推理 Local Infer", width=590, height=160)

        tk.Label(self.local_infer, text="文本模型 Text Model").place(x=5, y=5)
        self.qwen_api_url = ttk.Entry(self.local_infer, width=50)
        self.qwen_api_url.insert(0, configure_settings['local']['text'])
        self.qwen_api_url.place(x=150, y=5)

        tk.Label(self.local_infer, text="GPT-SoVITS (TTS)").place(x=5, y=35)
        self.gsv_api_url = ttk.Entry(self.local_infer, width=50)
        self.gsv_api_url.insert(0, configure_settings['local']['gsv'])
        self.gsv_api_url.place(x=150, y=35)

        tk.Label(self.local_infer, text="语音识别 Recognition").place(x=5, y=65)
        self.recognition_api_tool = ttk.Combobox(self.local_infer, width=10, values=['whisper'], state="readonly")
        self.recognition_api_tool.set(configure_settings['local']['rec']['tool'])
        self.recognition_api_tool.place(x=150, y=65)

        self.recognition_api_url = ttk.Entry(self.local_infer, width=36)
        self.recognition_api_url.insert(0, configure_settings['local']['rec']['url'])
        self.recognition_api_url.place(x=250, y=65)

        tk.Label(self.local_infer,
                 text="格式化说明：\n"
                      "     1. {year}表当前年份"
                      "\t 2. {ip}表当前设备IP", justify=tk.LEFT, anchor=tk.W, fg="green").place(x=5, y=95)

        self.local_infer.place(x=5, y=160)

        tk.Label(self.inference_frame, text="文本转语音 (TTS): ").place(x=5, y=320)
        self.tts_value = tk.StringVar(self)
        self.tts_value.set(configure['settings']['tts']['way'])
        self.tts_cloud = ttk.Radiobutton(self.inference_frame, text="云端 Cloud",
                                         variable=self.tts_value, value="cloud")
        self.tts_cloud.place(x=200, y=320)

        self.tts_local = ttk.Radiobutton(self.inference_frame, text="本地 Local",
                                         variable=self.tts_value, value="local")
        self.tts_local.place(x=300, y=320)

        tk.Label(self.inference_frame, text="文本输出 (Text)：").place(x=5, y=350)
        self.text_value = tk.StringVar(self)
        self.text_value.set(configure['settings']['text']['way'])
        self.text_cloud = ttk.Radiobutton(self.inference_frame, text="云端 Cloud",
                                          variable=self.text_value, value="cloud")
        self.text_cloud.place(x=200, y=350)

        self.text_local = ttk.Radiobutton(self.inference_frame, text="本地 Local",
                                          variable=self.text_value, value="local")
        self.text_local.place(x=300, y=350)

        tk.Label(self.inference_frame, text="语音识别 (Recognition)").place(x=5, y=380)
        self.rec_value = tk.StringVar(self)
        self.rec_value.set(configure['settings']['rec'])
        self.rec_cloud = ttk.Radiobutton(self.inference_frame, text="云端 Cloud",
                                         variable=self.rec_value, value="cloud")
        self.rec_cloud.place(x=200, y=380)

        self.rec_local = ttk.Radiobutton(self.inference_frame, text="本地 Local",
                                         variable=self.rec_value, value="local")
        Balloon(
            self.rec_local,
            "【BUG】此推理模式有严重问题，不要使用！如果您选择该模式，"
            "您会收到一个Python Traceback，如果你可以解决，您可以前往GitHub发pull request来解决这个问题\n\n"
            "[BUG] This inference mode has serious problems, do not use! "
            "If you choose this mode, you will receive a Python Traceback, "
            "and if you can solve, please go to GitHub to submit a pull request to solve this problem",
            fg="yellow", bg="red")
        self.rec_local.place(x=300, y=380)
        ttk.Button(self.local_infer, text="保存设置 Save Settings", command=self.save_settings).place(x=430, y=100)

        self.bind_note = ttk.Notebook(self.bind_frame)
        self.note.add(self.bind_frame, text="绑定设置 Bind Settings")
        self.bind_plugin_frame = tk.Frame(self.bind_note)
        self.bind_animation_frame = tk.Frame(self.bind_note)
        self.bind_note.add(self.bind_plugin_frame, text="插件 Plugin")

        tk.Label(self.bind_plugin_frame, text="源Python文件路径 Source Python File Path").place(x=5, y=5)
        self.source_python_file_path = ttk.Entry(self.bind_plugin_frame, width=64)
        self.source_python_file_path.place(x=20, y=35)

        self.code_review = ScrolledText(self.bind_plugin_frame, width=80, height=5)
        self.code_review.place(x=5, y=65)
        colorizer.color_config(self.code_review)
        p = percolator.Percolator(self.code_review)
        d = colorizer.ColorDelegator()
        p.insertfilter(d)

        tk.Label(self.bind_plugin_frame, text="入口 Entrance").place(x=5, y=140)
        self.entrance_combo = ttk.Combobox(self.bind_plugin_frame, width=20, state="readonly")
        self.entrance_combo.bind("<<ComboboxSelected>>", lambda event: self.process_code())
        self.entrance_combo.place(x=100, y=140)

        self.entrance_description = tk.Entry(self.bind_plugin_frame, width=30)
        self.entrance_description.insert(0, "Description 描述")
        self.entrance_description.place(x=280, y=140)

        tk.Label(self.bind_plugin_frame, text="必选参数 Required Parameter：").place(x=5, y=175)

        ttk.Button(self.bind_plugin_frame,
                   text="选择 Choose",
                   command=lambda: self.select_file(self.source_python_file_path, self.code_review, self.process_code)
                   ).place(x=500, y=35)

        ttk.Button(self.bind_plugin_frame,
                   text="编译进程序中 Compile into program",
                   command=self.complie_plugin, width=80
                   ).pack(side=tk.BOTTOM)

        self.bind_note.add(self.bind_animation_frame, text="动画绑定 Animation Bind")

        tk.Label(self.bind_animation_frame, text="模型 Model").place(x=5, y=5)
        self.model_lists = os.listdir("./resources/model")
        self.model_list = ttk.Combobox(self.bind_animation_frame,
                                       width=20, state="readonly", values=self.model_lists)
        self.model_list.bind("<<ComboboxSelected>>", lambda event: self.fill_binder())
        self.model_list.set(configure['default'])
        self.model_list.place(x=100, y=5)

        tk.Label(self.bind_animation_frame, text="动画 Animation").place(x=5, y=35)
        self.animation_lists = ['ActionTouchHead', 'ActionClickChest']
        self.animation_binder = ttk.Combobox(self.bind_animation_frame,
                                             width=20, state="readonly", values=self.animation_lists)
        self.animation_binder.bind("<<ComboboxSelected>>", lambda event: self.fill_information())
        self.animation_binder.current(0)
        self.animation_binder.place(x=100, y=35)

        self.bind_parameter_frame = tk.LabelFrame(self.bind_animation_frame,
                                                  text="参数 Parameter",
                                                  width=585, height=320,
                                                  )

        tk.Label(self.bind_parameter_frame, text="坐标 Coordinate").place(x=5, y=0)
        tk.Label(self.bind_parameter_frame, text="min(X)").place(x=25, y=20)
        self.min_x = ttk.Entry(self.bind_parameter_frame, width=10)
        self.min_x.place(x=25, y=40)
        tk.Label(self.bind_parameter_frame, text="min(Y)").place(x=125, y=20)
        self.min_y = ttk.Entry(self.bind_parameter_frame, width=10)
        self.min_y.place(x=125, y=40)
        tk.Label(self.bind_parameter_frame, text="max(X)").place(x=225, y=20)
        self.max_x = ttk.Entry(self.bind_parameter_frame, width=10)
        self.max_x.place(x=225, y=40)
        tk.Label(self.bind_parameter_frame, text="max(Y)").place(x=325, y=20)
        self.max_y = ttk.Entry(self.bind_parameter_frame, width=10)
        self.max_y.place(x=325, y=40)
        self.auto_record_btn = ttk.Button(self.bind_parameter_frame,
                                          text="录入 Record",
                                          command=self.auto_record_position)
        self.auto_record_btn.place(x=450, y=30)

        mg = tk.Label(self.bind_parameter_frame, text="动作组 Motion Groups")
        Balloon(mg, text="绑定的动作组名\nMotion binding group name")
        mg.place(x=140, y=150)
        self.motion_binder = tk.Entry(self.bind_parameter_frame)
        mi = tk.Label(self.bind_parameter_frame, text="动作序 Motion Index")
        Balloon(mi, text="绑定的动作序号，从motions文件夹从上之下顺序，从0开始\n"
                         "Motion binding group index, from motions folder from top to bottom, beginning with 0")
        mi.place(x=300, y=150)
        self.motion_index_binder = tk.Entry(self.bind_parameter_frame)
        self.save_animation_btn = ttk.Button(self.bind_animation_frame,
                                             text="保存 Save",
                                             width=400,
                                             command=self.save_settings)
        self.save_animation_btn.pack(side=tk.BOTTOM)

        tk.Label(self.bind_parameter_frame, text="音频 Audio").place(x=5, y=70)
        self.audio_lists = os.listdir(f"./resources/voice/{configure_default}")
        self.audio_binder = ttk.Combobox(self.bind_parameter_frame,
                                         width=20, state="readonly", values=self.audio_lists)

        tk.Label(self.bind_parameter_frame, text="播放方式 Play Way").place(x=5, y=100)
        self.audio_type = ttk.Combobox(self.bind_parameter_frame,
                                       width=20, state="readonly", values=['random'])
        self.audio_type.current(0)
        self.audio_type.place(x=140, y=100)

        self.audio_binder.current(0)
        self.audio_binder.bind("<<ComboboxSelected>>", lambda event: self.fill_play_type())
        self.audio_binder.place(x=140, y=70)

        tk.Label(self.bind_parameter_frame, text="动画 Motion").place(x=5, y=130)
        self.motion_binder.place(x=140, y=130)
        self.motion_index_binder.place(x=300, y=130)

        self.bind_parameter_frame.place(x=5, y=80)

        self.bind_note.pack(fill=tk.BOTH, expand=True)

        self.intelligence_note.add(self.tts_parameter_frame, text="TTS 参数 Parameter")

        tpk = tk.Label(self.tts_parameter_frame, text="top_k: ")
        Balloon(tpk, "影响采样的概率(拉小复读机，拉大纯运气)\n"
                     "influence the probability of sampling (pull down to repeat, pull up to pure luck)")
        tpk.place(x=5, y=25)
        self.top_k_scale = tk.Scale(self.tts_parameter_frame, from_=1, to=100, orient=tk.HORIZONTAL, length=300)
        self.top_k_scale.set(configure['settings']['tts']['top_k'])
        self.top_k_scale.place(x=100, y=5)

        tpp = tk.Label(self.tts_parameter_frame, text="top_p: ")
        Balloon(tpp, "影响音频多样性(拉小太死板，拉大更多样)\n"
                     "influence the diversity of audio (pull down too stiff, pull up more variety)")
        tpp.place(x=5, y=65)
        self.top_p_scale = tk.Scale(self.tts_parameter_frame, from_=0.01, to=1.00,
                                    orient=tk.HORIZONTAL, length=300, resolution=0.01)
        self.top_p_scale.set(configure['settings']['tts']['top_p'])
        self.top_p_scale.place(x=100, y=45)

        tempt = tk.Label(self.tts_parameter_frame, text="temperature: ")
        Balloon(tempt,
                "影响音频随机性和变化度(拉小更固定，拉大更多变)\n"
                "influence the randomness and variation of audio (pull down more fixed, pull up more variation)")
        tempt.place(x=5, y=105)
        self.temperature_scale = tk.Scale(self.tts_parameter_frame, from_=0.01, to=1.00,
                                          orient=tk.HORIZONTAL, length=300, resolution=0.01)
        self.temperature_scale.set(configure['settings']['tts']['temperature'])
        self.temperature_scale.place(x=100, y=85)

        sp = tk.Label(self.tts_parameter_frame, text="speed: ")
        sp.place(x=5, y=145)
        Balloon(sp,
                "影响音频速度(拉小变慢，拉大变快)\n"
                "influence the speed of audio (pull down to slow, pull up to fast)")
        self.speed_scale = tk.Scale(self.tts_parameter_frame, from_=0.6, to=3.00,
                                    orient=tk.HORIZONTAL, length=300, resolution=0.01)
        self.speed_scale.set(configure['settings']['tts']['speed'])
        self.speed_scale.place(x=100, y=125)

        batch_size = tk.Label(self.tts_parameter_frame, text="Batch Size: ")
        batch_size.place(x=5, y=205)
        Balloon(batch_size,
                "影响推理速度(拉低减少GPU负荷，拉高增加GPU负荷)\n"
                "influence the speed of inference(pull down to reduce GPU load, pull up to increase GPU load)")
        self.batch_size_scale = tk.Scale(self.tts_parameter_frame, from_=1, to=50, orient=tk.HORIZONTAL, length=300)
        self.batch_size_scale.set(configure['settings']['tts']['batch_size'])
        self.batch_size_scale.place(x=100, y=185)

        bt = tk.Label(self.tts_parameter_frame, text="Batch Threshold: ")
        Balloon(bt, "性能优化阈值(拉低吃性能，拉高时间短)\n"
                    "performance optimization threshold (pull down to power performance, pull up to time short)")
        bt.place(x=5, y=245)
        self.batch_threshold_scale = tk.Scale(self.tts_parameter_frame,
                                              from_=0.01, to=1, orient=tk.HORIZONTAL, length=300, resolution=0.01)
        self.batch_threshold_scale.set(configure['settings']['tts']['batch_threshold'])
        self.batch_threshold_scale.place(x=100, y=225)

        self.parallel = tk.BooleanVar(self.tts_parameter_frame)
        self.parallel.set(configure['settings']['tts']['parallel'])
        self.parallel_check = ttk.Checkbutton(self.tts_parameter_frame, text="并行推理 Parallel Inference",
                                              variable=self.parallel)
        Balloon(self.parallel_check,
                "影响推理速度(开启更快消耗高，关闭更慢消耗少)\n"
                "influence the speed of inference (open faster consume high, close slower consume less)")
        self.parallel_check.place(x=5, y=350)

        ttk.Button(self.tts_parameter_frame, text="保存设置 Save Settings", command=self.save_settings).place(x=430, y=350)

        self.intelligence_note.pack(fill=tk.BOTH, expand=True)

        self.note.add(self.character_frame, text="角色设定 Character Sets")

        self.sets_tree = ttk.Treeview(self.character_frame,
                                      columns=("Character", "Role", "Prompt"), show="headings",
                                      selectmode="browse")
        self.sets_tree.heading("Character", text="角色 Characater", anchor='center')
        self.sets_tree.column("Character", width=70, anchor='center')
        self.sets_tree.heading("Role", text="权限 Role")
        self.sets_tree.column("Role", width=40, anchor='center')
        self.sets_tree.heading("Prompt", text="描述 Prompt")
        self.sets_tree.column("Prompt", width=390)
        self.sets_tree.bind("<Double-1>", self.on_double_click)
        self.sets_tree.place(x=5, y=5, w=590, h=300)
        self.add_one_prompt = ttk.Button(
            self.character_frame, text="添加词条 Add Prompt", command=lambda: self.change_prompt("add"))
        self.add_one_prompt.place(x=5, y=310)
        self.remove_one_prompt = ttk.Button(
            self.character_frame, text="删除词条 Remove Prompt", command=lambda: self.change_prompt("remove"))
        self.remove_one_prompt.place(x=220, y=310)
        self.refresh_prompts_button = ttk.Button(
            self.character_frame, text="刷新词条 Refresh Prompts", command=lambda: self.refresh_prompt())
        self.refresh_prompts_button.place(x=435, y=310)

        self.note.add(self.about_frame, text="关于 About")
        tk.Label(self.about_frame, text="AI 桌宠相关说明 AI Desktop Pet explanation", font=('微软雅黑', 20)).pack()

        self.use_open_sources = tk.LabelFrame(self.about_frame, text="引用开源库 Quote Open Sources", width=590, height=100)
        self.quote_live2d_py = tk.Label(self.use_open_sources, text='Live2D-Py(MIT)', fg="blue", font=('微软雅黑', 13))
        self.quote_live2d_py.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/Arkueid/live2d-py.git"))
        self.quote_live2d_py.place(x=5, y=0)
        self.quote_pyqt5 = tk.Label(self.use_open_sources, text='PyQt5(LGPL v3.0)', fg="blue", font=('微软雅黑', 13))
        self.quote_pyqt5.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/PyQt5/PyQt.git"))
        self.quote_pyqt5.place(x=180, y=0)
        self.quote_opengl = tk.Label(self.use_open_sources, text='PyOpenGL', fg="blue", font=('微软雅黑', 13))
        self.quote_opengl.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/mcfletch/pyopengl"))
        self.quote_opengl.place(x=365, y=0)
        self.quote_python = tk.Label(self.use_open_sources, text='Python(PSF)', fg="blue", font=('微软雅黑', 13))
        self.quote_python.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/python/cpython.git"))
        self.quote_python.place(x=5, y=30)
        self.quote_ffmpeg = tk.Label(self.use_open_sources, text='FFmpeg(LGPL v2.1+)', fg="blue", font=('微软雅黑', 13))
        self.quote_ffmpeg.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/FFmpeg/FFmpeg.git"))
        self.quote_ffmpeg.place(x=180, y=30)
        self.quote_self = tk.Label(self.use_open_sources,
                                   text='AI Desktop Pet(LGPL v3.0)', fg="blue", font=('微软雅黑', 13))
        self.quote_self.bind("<Button-1>",
                             lambda e: webbrowser.open("https://github.com/grass-tech/AgenticCompanion.git"))
        self.quote_self.place(x=365, y=30)
        self.use_open_sources.place(x=5, y=50)

        self.refresh_prompt()
        self.fill_play_type()
        self.refresh_gui()
        self.fill_information()

        self.note.pack(fill=tk.BOTH, expand=True)

    @staticmethod
    def auto_record_position():
        messagebox.showinfo(
            "帮助 Help",
            "开始录入：你需要在您的角色上点击录入。点击两次，第一次为最小值，第二次为最大值\n"
            "Start recording: You need to click on your character to record. "
            "Click twice, the first is the minimum value, the second is the maximum value")
        configure['record']['enable_position'] = True
        configure['record']['position'] = [
            -1, -1, -1, -1
        ]

    def fill_play_type(self):
        selected = self.audio_binder.get()
        values = os.listdir(f"./resources/voice/{configure_default}/{selected}")
        values.append("random")
        self.audio_type.configure(values=values)

    def fill_information(self):
        self.audio_type.set(get_configure_actions()[self.animation_binder.get()]['play_type'])
        self.audio_binder.set(get_configure_actions()[self.animation_binder.get()]['play'])
        self.motion_binder.delete(0, tk.END)
        self.motion_index_binder.delete(0, tk.END)
        if (cap := get_configure_actions()[self.animation_binder.get()]['motion']) is not None:
            self.motion_binder.insert(0, str(cap).split(":")[0])
            self.motion_index_binder.insert(0, str(cap).split(":")[1])
        else:
            self.motion_binder.insert(0, "")

        self.min_x.delete(0, tk.END)
        self.min_y.delete(0, tk.END)
        self.max_x.delete(0, tk.END)
        self.max_y.delete(0, tk.END)

        self.min_x.insert(0, get_configure_actions()[self.animation_binder.get()]['position'][0])
        self.min_y.insert(0, get_configure_actions()[self.animation_binder.get()]['position'][2])
        self.max_x.insert(0, get_configure_actions()[self.animation_binder.get()]['position'][1])
        self.max_y.insert(0, get_configure_actions()[self.animation_binder.get()]['position'][3])

    def fill_binder(self):
        if self.model_list.get() not in configure['model'].keys():
            load_template_model(self.model_list.get())

    def complie_plugin(self):
        template = {
            "type": "function",
            "function": {
                "name": self.entrance_combo.get(),
                "description": self.entrance_description.get(),
                "parameters": {
                    "type": "object",
                    "properties": {}
                },
                "required": []
            }
        }
        for var_name, value in self.required_check_button_value.items():
            if value['value'].get():
                template['function']['required'].append(var_name)
            template['function']['parameters']['properties'].update({
                var_name: {
                    "type": value['type'].get(),
                    "description": value['description'].get()
                }
            })

        with open("./resources/functions.json", "r", encoding="utf-8") as ff:
            original: list = json.load(ff)
            original_functions = {}
            for function in original:
                original_functions.update({function['function']['name']: function})
            ff.close()

        if self.entrance_combo.get() in original_functions.keys():
            original.remove(original_functions[self.entrance_combo.get()])
        os.remove("./resources/functions.json")
        with open("./resources/functions.json", "w", encoding="utf-8") as ff:
            original.append(template)
            json.dump(original, ff, indent=3, ensure_ascii=False)
            ff.close()

        with open("./intelligence/plugin/__init__.py", "r", encoding="utf-8") as of:
            original_code = of.read()
            of.close()
        to_be_complied_code = self.code_review.get(1.0, tk.END)
        if to_be_complied_code.strip() == "":
            return

        if self.entrance_combo.get() in original_functions.keys():
            original_code = RemoveFunctionTransformer(self.entrance_combo.get()).remove(original_code)
        import_matches = re.findall(
            r'^\s*(import\s+[\w\s,\.]+|from\s+\w+\s+import\s+[\w\s,\.]+)$',
            to_be_complied_code,
            re.MULTILINE)
        for match in import_matches:
            if match.strip() not in original_code:
                original_code = match + original_code + '\n'
            to_be_complied_code = to_be_complied_code.replace(match, '')
        original_code += f"\n\n{to_be_complied_code}"
        with open("./intelligence/plugin/__init__.py", "w", encoding="utf-8") as wnf:
            wnf.write(original_code)
            wnf.close()
        intelligence.text.reload_tools()
        messagebox.showinfo("编译完成 Finish compling", "编译完成！Finished compling")

    def process_code(self):
        self.entrance_combo.configure(state=tk.NORMAL)
        type_mapping = {
            'str': 'string',
            'int': 'integer',
            'bool': 'boolean',
            'float': 'float',
            'unknown': 'unknown'
        }

        matches = re.findall(r'def\s+(\w+)\s*\(([^)]*)\)', self.code_review.get(1.0, tk.END))

        if self.is_selected_file:
            self.function_names = []
        x, y = 20, 200
        for value in self.required_check_button_value.values():
            value['type'].place_forget()
            value['description'].place_forget()
            value['check'].place_forget()
        self.required_check_button_value = {}
        for match in matches:
            function_name = match[0]
            if self.is_selected_file:
                self.function_names.append(function_name)
            parameters = match[1].split(',')
            parameters = [param.strip() for param in parameters]

            for param in parameters:
                required_value = tk.BooleanVar(self)
                if '=' in param:
                    required_value.set(False)
                    key, value = param.split('=')
                    key = key.strip()
                    value = value.strip()
                    if ':' in key:
                        param_name, param_type = key.split(':')
                        param_name = param_name.strip()
                    else:
                        param_name = key

                    if value.startswith('"') and value.endswith('"'):
                        param_type = 'string'
                    elif value.isdigit():
                        param_type = 'integer'
                    elif re.match(r'^-?\d+\.\d+$', value):
                        param_type = 'float'
                    elif value.lower() in ['true', 'false']:
                        param_type = 'boolean'
                    else:
                        param_type = 'unknown'

                else:
                    required_value.set(True)
                    if ':' in param:
                        param_name, param_type = param.split(':')
                        param_name = param_name.strip()
                        param_type = param_type.strip()
                    else:
                        param_name = param
                        param_type = 'unknown'
                    param_type = type_mapping.get(param_type, param_type)
                try:
                    selected_function = self.function_names[self.function_names.index(self.entrance_combo.get())]
                except ValueError:
                    selected_function = self.function_names[0]
                if (not param_name or
                        selected_function != function_name):
                    continue
                check = ttk.Checkbutton(
                    self.bind_plugin_frame,
                    text=param_name,
                    variable=required_value,
                    onvalue=True, offvalue=False
                )
                type_combo = ttk.Combobox(
                    self.bind_plugin_frame,
                    values=['string', 'integer', 'float', 'boolean'],
                    width=6, state='readonly',
                )
                if param_type != "unknown":
                    type_combo.set(param_type)
                value_description = tk.Entry(self.bind_plugin_frame, width=10)
                value_description.insert(0, "描述 Description")
                self.required_check_button_value.update(
                    {param_name: {'check': check,
                                  'value': required_value,
                                  'description': value_description,
                                  'type': type_combo}})
                type_combo.place(x=x + 120, y=y)
                value_description.place(x=x + 120 + 70, y=y)
                check.place(x=x, y=y)
                x += 270
                if x > 400:
                    x = 20
                    y += 25

        if self.is_selected_file:
            self.entrance_combo.configure(values=self.function_names)
            self.entrance_combo.current(0)
        self.entrance_combo.configure(state="readonly")
        self.is_selected_file = False

        function_doc_string = "描述 Description"
        extraction_doc = ExtractFunctionDocstring(self.entrance_combo.get()).extract(self.code_review.get(1.0, tk.END))
        if extraction_doc is not None:
            function_doc_string = extraction_doc
        self.entrance_description.delete(0, tk.END)
        self.entrance_description.insert(0, function_doc_string)

    def select_file(self,
                    fill_box: tk.Entry | tk.Text, content_box: ScrolledText, running_func=None):
        self.is_selected_file = True
        fill_box.delete(0, tk.END)
        fill_box.insert(0, filedialog.askopenfilename(
            filetypes=[("Python Source", "*.py")],
            title="选择文件 Select File"
        ))
        content_box.delete(0.0, tk.END)
        with open(fill_box.get(), "r", encoding="utf-8") as cf:
            content_box.insert(0.0, cf.read())
            cf.close()
        if running_func is not None:
            running_func()

    def refresh_gui(self):
        self.globe_mouse_penetration_value.set(configure['settings']['penetration']['enable'])
        self.penetration_start_value.set(configure['settings']['penetration']['start'])

        if (self.min_x.get() == "-1" or self.max_x.get() == "-1" or
                self.min_y.get() == "-1" or self.max_y.get() == "-1" or
                configure['record']['enable_position']):
            self.min_x.delete(0, tk.END)
            self.max_x.delete(0, tk.END)
            self.min_y.delete(0, tk.END)
            self.max_y.delete(0, tk.END)

            self.min_x.insert(0, configure['record']['position'][0])
            self.min_y.insert(0, configure['record']['position'][1])
            self.max_x.insert(0, configure['record']['position'][2])
            self.max_y.insert(0, configure['record']['position'][3])

        self.after(100, self.refresh_gui)

    def refresh_prompt(self):
        self.sets_tree.delete(*self.sets_tree.get_children())
        if configure['default'] == "origin":
            return
        if not os.path.exists(f"./intelligence/prompts/{configure['default']}.json"):
            with open(f"./intelligence/prompts/{configure['default']}.json", "w", encoding="utf-8") as lf:
                json.dump({}, lf, ensure_ascii=False, indent=3)
                lf.close()
        with open(f"./intelligence/prompts/{configure['default']}.json", "r", encoding="utf-8") as df:
            for role, content in json.load(df).items():
                self.sets_tree.insert("", "end", values=(configure['default'], role, content))
            f.close()

    def change_prompt(self, run_type: typing.Literal['add', 'remove']):
        if configure['default'] == "origin":
            return
        if run_type == "add":
            self.sets_tree.insert("", "end", values=(f"{configure['default']}", "Role", "Content"))
        else:
            self.sets_tree.delete(self.sets_tree.selection()[0])
        be_updated_prompts = {}
        for child_id in self.sets_tree.get_children():
            prompts = self.sets_tree.item(child_id)['values']
            be_updated_prompts.update({prompts[1]: prompts[2]})
        with open(f"./intelligence/prompts/{configure['default']}.json", "w", encoding="utf-8") as sf:
            json.dump(be_updated_prompts, sf, ensure_ascii=False, indent=4)
            sf.close()
        if run_type == "remove":
            if not be_updated_prompts:
                os.remove(f"./intelligence/prompts/{configure['default']}.json")

    def on_double_click(self, event):
        selected_item = self.sets_tree.selection()[0]
        column = self.sets_tree.identify_column(event.x)
        col_index = int(column.replace('#', '')) - 1

        entry_edit = ScrolledText(self, width=15, bg="black", fg='#00FF00')

        def set_entry_position():
            return self.sets_tree.bbox(selected_item, column)

        bbox = set_entry_position()
        entry_edit.place(x=bbox[0] + 5, y=bbox[1] + 30, w=bbox[2], h=bbox[3] + 20)

        entry_edit.insert(1.0, self.sets_tree.item(selected_item)['values'][col_index])
        entry_edit.focus()

        def save_edit():
            self.sets_tree.item(
                selected_item,
                values=list(
                    self.sets_tree.item(selected_item)['values'])[:col_index] + [
                    entry_edit.get(1.0, tk.END).replace("\n", "")
                ] + list(
                    self.sets_tree.item(selected_item)['values'])[col_index + 1:])
            entry_edit.place_forget()
            be_updated_prompts = {}
            for child_id in self.sets_tree.get_children():
                prompts = self.sets_tree.item(child_id)['values']
                if not be_updated_prompts.get(prompts[0]):
                    be_updated_prompts.update({prompts[0]: {}})
                be_updated_prompts[prompts[0]].update({prompts[1]: prompts[2]})
            for character, prompt in be_updated_prompts.items():
                with open(f"./intelligence/prompts/{character}.json", "w", encoding="utf-8") as df:
                    json.dump(prompt, df, indent=3, ensure_ascii=False)
                    df.close()

        entry_edit.bind("<FocusOut>", lambda e: save_edit())
        entry_edit.bind("<Return>", lambda e: save_edit())

    def change_character(self, character):
        if character in configure['model'].keys() or character == "origin":
            configure['default'] = character
        else:
            messagebox.showwarning("警告 Warning",
                                   f"资源中没有{character}。请前往动画绑定进行绑定后重试！\n"
                                   f"{character} not found in resources. Please bind it first!")
        configure['name'] = self.pet_nickname_entry.get()
        configure['voice_model'] = self.voice_model_lists.get()

        intelligence.text.reload_memories(character)

        with open("./resources/configure.json", "w", encoding="utf-8") as sf:
            json.dump(configure, sf, indent=3, ensure_ascii=False)
            sf.close()

    def change_refer_text(self, event):
        refer_text = MODULE_INFO[self.voice_model_lists.get()][3]
        self.voice_text_entry.delete(0, tk.END)
        self.voice_text_entry.insert(0, refer_text)
        configure['voice_model'] = self.voice_model_lists.get()

        with open("./resources/configure.json", "w", encoding="utf-8") as sf:
            json.dump(configure, sf, indent=3, ensure_ascii=False)
            sf.close()

    def play_refer_audio(self):
        if self.tts_value.get() == "local":
            if not intelligence.VoiceSwitch:
                return
            lang, t = self.voice_text_entry.get().split(":")
            intelligence.voice_change(self.voice_model_lists.get(), MODULE_INFO)
            audio_bytes = intelligence.gsv_voice_generator(t, lang, self.voice_model_lists.get(), MODULE_INFO)
        else:
            audio_bytes, duration = intelligence.ali_voice_generator(self.voice_text_entry.get())

        with wave.open(io.BytesIO(audio_bytes), 'rb') as wf:
            p = pyaudio.PyAudio()
            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()), channels=wf.getnchannels(),
                            rate=wf.getframerate(), output=True)
            data = wf.readframes(1024)
            while data:
                stream.write(data)
                data = wf.readframes(1024)
            stream.stop_stream()
            stream.close()
            p.terminate()

    def save_settings(self):
        configure['settings']['tts']['way'] = self.tts_value.get()
        configure['settings']['tts']['top_k'] = self.top_k_scale.get()
        configure['settings']['tts']['top_p'] = self.top_p_scale.get()
        configure['settings']['tts']['temperature'] = self.temperature_scale.get()
        configure['settings']['tts']['speed'] = self.speed_scale.get()
        configure['settings']['tts']['batch_size'] = self.batch_size_scale.get()
        configure['settings']['tts']['batch_threshold'] = self.batch_threshold_scale.get()
        configure['settings']['tts']['parallel'] = self.parallel.get()

        configure['settings']['text']['way'] = self.text_value.get()
        # configure['settings']['rec'] = self.rec_value.get()
        if self.rec_value.get() == "local":
            with open("./resources/unsolved_traceback/whisper_api", "r", encoding="utf-8") as uf:
                api_log = uf.read()
            messagebox.showerror("Python Traceback LOGS", api_log)

        configure['settings']['local']['text'] = self.qwen_api_url.get()
        configure['settings']['local']['gsv'] = self.gsv_api_url.get()
        configure['settings']['local']['rec']['tool'] = self.recognition_api_tool.get()
        configure['settings']['local']['rec']['url'] = self.recognition_api_url.get()
        configure['settings']['cloud']['aliyun'] = self.aliyun_apikey_entry.get()
        configure['settings']['cloud']['xunfei']['id'] = self.xunfei_apiid_entry.get()
        configure['settings']['cloud']['xunfei']['key'] = self.xunfei_apikey_entry.get()
        configure['settings']['cloud']['xunfei']['secret'] = self.xunfei_apisecret_entry.get()

        configure['record']['position'] = [-1, -1, -1, -1]

        position = [int(self.min_x.get()), int(self.max_x.get()), int(self.min_y.get()), int(self.max_y.get())]
        configure['model'][self.model_list.get()]['action'][
            self.animation_binder.get()]['position'] = position
        configure['model'][self.model_list.get()]['action'][
            self.animation_binder.get()]['motion'] = f"{self.motion_binder.get()}:{self.motion_index_binder.get()}"
        configure['model'][self.model_list.get()]['action'][
            self.animation_binder.get()]['play'] = self.audio_binder.get()
        configure['model'][self.model_list.get()]['action'][
            self.animation_binder.get()]['play_type'] = self.audio_type.get()

        with open("./resources/configure.json", "w", encoding="utf-8") as sf:
            json.dump(configure, sf, indent=3, ensure_ascii=False)
            sf.close()

    def change_watermark(self, event=None):
        watermark_value = int(self.watermark_scale.get())
        watermark_param = self.watermark_combo.get()
        self.watermark_scale.configure(from_=param_dict[self.watermark_combo.get()]['min'],
                                       to=param_dict[self.watermark_combo.get()]['max'])
        self.change_configure(f"{watermark_param};{watermark_value}", "watermark")

    def change_translate(self):
        configure['settings']['translate'] = \
            (f"{re.sub(r'[\u4e00-\u9fa5]+[\s+]', '', self.translation_class.get()).lower()}."
             f"{re.sub(r'[\u4e00-\u9fa5]+[\s+]', '', self.translation_tool.get()).lower()}")
        with open("./resources/configure.json", "w", encoding="utf-8") as cf:
            json.dump(configure, cf, ensure_ascii=False, indent=3)
            cf.close()

    def change_translation_tool(self, event):
        if self.translation_class.get() == "爬虫 Spider":
            self.translation_tool.configure(values=["必应 Bing"])
        elif self.translation_class.get() == "人工智能 AI":
            self.translation_tool.configure(values=["通义千问 Tongyi"])
        self.translation_tool.current(0)
        self.change_translate()

    def change_configure(self, value, relative):
        temp_dict = configure

        for key in relative.split(".")[:-1]:
            if key not in temp_dict:
                temp_dict[key] = {}
            temp_dict = temp_dict[key]

        if relative.split("."):
            if "penetration" in relative and "start" in relative:
                temp_dict["start"] = self.penetration_start_value.get()
            last_key = relative.split(".")[-1]
            temp_dict[last_key] = value

        with open("./resources/configure.json", "w", encoding="utf-8") as cf:
            json.dump(configure, cf, ensure_ascii=False, indent=3)
            cf.close()

    def io_configure(self, value: str, relative=None, behave: object = int):
        if "{" in value and "}" in value:
            temp_dict = configure

            for key in relative.split(".")[:-1]:
                if key not in temp_dict:
                    temp_dict[key] = {}
                temp_dict = temp_dict[key]

            if relative.split("."):
                last_key = relative.split(".")[-1]
                if temp_dict[last_key]:
                    if value == "{adult}":
                        self.adult_lists.configure(state=tk.DISABLED)
                    temp_dict[last_key] = 0 if behave == int else False
                else:
                    if value == "{adult}":
                        self.adult_lists.configure(state="readonly")
                    temp_dict[last_key] = 1 if behave == int else True
        else:
            if value not in configure['settings']['disable']:
                configure_settings['disable'].append(value)
                if relative is not None:
                    relative()
            else:
                configure_settings['disable'].remove(value)
                if relative is not None:
                    relative()

        with open("./resources/configure.json", "w", encoding="utf-8") as cf:
            json.dump(configure, cf, ensure_ascii=False, indent=3)
            cf.close()


# 主程序
class DesktopTop(QOpenGLWidget):
    def __init__(self):
        super().__init__()
        # 窗口大小
        width = 400
        height = 400
        # 设置标题 Set Title
        self.setWindowTitle("AgenticCompanion - Character Mainloop")
        # 设置图标 Set icon
        self.setWindowIcon(QIcon("logo.ico"))
        # 设置属性 Set Attribute
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # self.setWindowOpacity(0.4)
        self.setMouseTracking(True)
        # 调整大小 Set Resize
        self.resize(width, height)

        # 基础变量和开关 Variables and Switches
        self.speaking_lists: list[bool] = []
        self.turn_count = self.among = 0
        self.click_in_area = self.click_x = self.click_y = -1
        self.is_penetration = self.is_playing_animation = self.is_movement = False
        self.enter_position = self.drag_position = None
        self.random_cancel_penetration = self.image_path = self.direction = self.last_pos = None
        self.pet_model: live2d.LAppModel | None = None

        # 屏幕中心坐标 Center of the screen
        self.screen_geometry = QApplication.desktop().availableGeometry()
        x = (self.screen_geometry.width() - self.width()) // 2
        y = self.screen_geometry.height() - self.height()
        self.move(x, y + 15)  # 15是距离任务栏的距离 15 is distance from the taskbar

        self.recognize_thread = RecognitionThread(self)
        self.recognize_thread.result.connect(self.recognition_success)

        # 界面构建 GUI build
        # 对话输入框 Conversation input box
        self.conversation_entry = QTextEdit(self)
        self.conversation_entry.installEventFilter(self)
        self.conversation_entry.setPlaceholderText(f"{configure['name']}等待您的聊天……")
        self.conversation_entry.setGeometry(QRect((width - 350) // 2, height - 75, 200, 75))
        # 发送聊天按钮 Send chat button
        self.conversation_button = QPushButton(self)
        self.conversation_button.setText("聊天(Shift + Enter)")
        self.conversation_button.setGeometry(QRect((width - 350) // 2 + 200, height - 75, 150, 25))
        # 清除记忆的按钮 Clear memories button
        self.clear_memories_button = QPushButton(self)
        self.clear_memories_button.setText("清除记忆(Alt + C)")
        self.clear_memories_button.setGeometry(QRect((width - 350) // 2 + 200, height - 50, 150, 25))
        # 媒体按钮 Media button
        self.media_button = QPushButton(self)
        self.media_button.setText("截屏(Alt + S)")
        self.media_button.setGeometry(QRect((width - 350) // 2 + 200, height - 25, 150, 25))
        # 聊天框 Chat box
        self.chat_box = QTextEdit(self)
        self.chat_box.setReadOnly(True)
        self.chat_box.setFont(QFont("微软雅黑", 11))
        self.chat_box.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.chat_box.setGeometry(QRect((width - 350) // 2, height - 175, 350, 100))
        # 设置样式 Set style
        self.conversation_entry.setStyleSheet("background-color: rgba(255, 255, 255, 150);")
        self.conversation_button.setStyleSheet("background-color: rgba(255, 255, 255, 150);")
        self.media_button.setStyleSheet("background-color: rgba(255, 255, 255, 150);")
        self.clear_memories_button.setStyleSheet("background-color: rgba(255, 255, 255, 150);")
        self.chat_box.setStyleSheet("background-color: rgba(255, 255, 255, 180); border: 1px solid black;")

        # 绑定函数 Bind functions
        self.conversation_button.clicked.connect(lambda checked: self.have_conversation(None))
        self.media_button.clicked.connect(self.capture_screen)
        self.clear_memories_button.clicked.connect(self.clear_memories)
        # 设置不可见 Set non-visible
        self.conversation_entry.setVisible(False)
        self.conversation_button.setVisible(False)
        self.media_button.setVisible(False)
        self.clear_memories_button.setVisible(False)
        self.chat_box.setVisible(False)

        self.is_transparent_raise = False

        # 定时器
        self.look_timer = QTimer(self)
        self.look_timer.timeout.connect(self.look_for_me)
        if "media" not in configure['settings']['disable']:
            self.look_timer.start(random.randint(
                    configure['settings']['understand']['min'] // 2,
                    configure['settings']['understand']['max'] // 2) * 1000)

        # 桌宠预备 Pet Preparation
        if configure_voices['welcome']:
            SpeakThread(
                self,
                f"./resources/voice/{configure_default}/welcome/{random.choice(configure_voices['welcome'])}"
            ).start()

        self.show()

    # GUI功能性配置 GUI functional configuration
    def set_mouse_transparent(self, is_transparent: bool):
        """设置鼠标穿透 (透明部分可以直接穿过)"""
        if self.is_transparent_raise:
            return
        window_handle = int(self.winId())
        try:
            SetWindowLong = ctypes.windll.user32.SetWindowLongW
            GetWindowLong = ctypes.windll.user32.GetWindowLongW

            current_exstyle = GetWindowLong(window_handle, GWL_EXSTYLE)
            if is_transparent:
                # 添加WS_EX_TRANSPARENT样式以启用鼠标穿透 Add WS_EX_TRANSPARENT style to enable mouse transparency
                new_exstyle = current_exstyle | WS_EX_TRANSPARENT
            else:
                # 移除WS_EX_TRANSPARENT样式以禁用鼠标穿透 Remove WS_EX_TRANSPARENT style to disable mouse transparency
                new_exstyle = current_exstyle & ~WS_EX_TRANSPARENT

            # 应用新的样式 Apply the new style
            SetWindowLong(window_handle, GWL_EXSTYLE, new_exstyle)
        except Exception as e:
            self.is_transparent_raise = True
            QMessageBox.warning(
                self,
                "警告 Warning",
                "无法开启透明部分鼠标穿透\n请将此错误报告给作者 \n"
                f"Failed to set window transparent for mouse events\n"
                f"Please report this error to the author\n\n"
                f"=====================================\n"
                f"错误信息 Error information： \n{type(e).__name__}: {e}\n"
                f"=====================================\n\n"
                f"你将不能点击透明部分的区域！\n"
                f"You will not be able to click on the transparent area!\n")

    def set_window_below_taskbar(self):
        """设置低于任务栏(高于其它除了任务栏的应用)"""
        hwnd = self.winId().__int__()
        taskbar_hwnd = win32gui.FindWindow("Shell_TrayWnd", None)

        win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
        win32gui.SetWindowPos(hwnd, taskbar_hwnd, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)

    # 功能 Functions
    def look_for_me(self):
        self.look_timer.stop()
        image_path = runtime.capture()
        RFST = MediaUnderstandThread(self, image_path)
        RFST.result.connect(lambda text: self.conversation_display(text, True))
        RFST.start()
        if "media" not in configure['settings']['disable']:
            self.look_timer.start(random.randint(
                configure['settings']['understand']['min'],
                configure['settings']['understand']['max']) * 1000)

    def capture_screen(self):
        if "media" in configure['settings']['disable']:
            return
        self.conversation_entry.setText(str(self.conversation_entry.toPlainText()) + "$[图片]$")
        self.image_path = runtime.capture()

    # 语音识别 Recognition
    def recognize(self):
        if "rec" in configure['settings']['disable']:
            return
        if self.recognize_thread.isRunning():
            self.recognize_thread.wait()
        self.recognize_thread.start()

    def recognition_success(self, result: str):
        speech_rec.statued()

        if configure['name'] in result or configure_default in result:
            # 临时对话不启用一些界面 Temporary dialog does not enable some interfaces
            self.change_status_for_conversation("hide", False)
            self.chat_box.setVisible(True)

            self.have_conversation(result, True)
        logger(f"子应用 - 语音识别 语音呼唤成功\n"
               f"Sub-Application - Voice Recognition Success: {result}\n"
               f"  Message: {result}\n\n"
               f"  Origin: {json.dumps(result, indent=3, ensure_ascii=False)}", logs.API_PATH)

    @staticmethod
    def recognition_failure(error, code):
        logger(f"子应用 - 语音识别 发生错误 {code}:{error}\n"
               f"Sub-Application - Voice Recognition Error: {code}:{error}\n", logs.API_PATH)

    @staticmethod
    def recognition_closure():
        logger("子应用 - 语音识别已关闭\n"
               "Sub-Application - Voice Recognition Closed\n", logs.API_PATH)

    # 对话相关 Conversation related
    def open_close_conversation(self):
        if self.conversation_entry.isVisible():
            self.change_status_for_conversation("hide")
        else:
            self.change_status_for_conversation("show")

    def change_status_for_conversation(self,
                                       status: typing.Literal['hide', 'show'],
                                       enable_chat_box: bool = True
                                       ):
        if status == "show":
            self.conversation_entry.setVisible(True)
            self.conversation_button.setVisible(True)
            self.clear_memories_button.setVisible(True)
            self.media_button.setVisible(True)
            if enable_chat_box:
                self.chat_box.setVisible(True)
        else:
            self.conversation_entry.setVisible(False)
            self.conversation_button.setVisible(False)
            self.clear_memories_button.setVisible(False)
            self.media_button.setVisible(False)
            if enable_chat_box:
                self.chat_box.setVisible(False)

    def conversation_display(self, text: tuple, temp_action: bool = False):
        def __processor(html_text: str):
            """Process Markdown text scale"""
            def __closure(match):
                original_tag = match.group(1)
                default_width = 1024
                default_height = 1024
                new_width = int(default_width * 0.35)
                new_height = int(default_height * 0.35)
                if 'width=' not in original_tag:
                    original_tag += f' width="{new_width}"'
                else:
                    original_tag = re.sub(r'(width=["\'])(\d+)(["\'])', rf'\g<1>{new_width}\g<3>', original_tag)
                if 'height=' not in original_tag:
                    original_tag += f' height="{new_height}"'
                else:
                    original_tag = re.sub(r'(height=["\'])(\d+)(["\'])', rf'\g<1>{new_height}\g<3>', original_tag)

                return f'{original_tag} />'

            return re.sub(r'(<img[^>]*)/', __closure, html_text)

        def __exec(information: list):
            """
            :param information: 0 -> wav_bytes 1 -> duration
            """
            def __closure():
                # 闭包函数
                nonlocal text_begin, is_emotion
                flot_timer.stop()
                if isinstance(text_begin, int):
                    if text_begin < len(common_text) - 1:
                        text_begin += 1
                        self.chat_box.setVisible(True)
                        self.chat_box.setText(str(self.chat_box.toPlainText()) + common_text[text_begin:text_begin + 1])
                        self.chat_box.moveCursor(self.chat_box.textCursor().End)
                        # 处理括号之间的表情等内容 Process the contents between brackets
                        if common_text[text_begin:text_begin + 1] in (")", "]", "）", "】") and is_emotion:
                            is_emotion = False
                        if common_text[text_begin:text_begin + 1] in ("(", "[", "（", "【") or is_emotion:
                            is_emotion = True
                            flot_timer.start(35)
                        else:
                            is_emotion = False
                            flot_timer.start(125)
                    else:
                        text_begin = "END"
                        flot_timer.start(1000 + (
                            max(0, int(information[1] - (time.time() - start_time) * 1000))
                            if intelligence.VoiceSwitch else
                            100
                            )
                        )

                else:
                    self.chat_box.clear()
                    self.chat_box.setHtml(markdown_text)
                    self.chat_box.moveCursor(self.chat_box.textCursor().End)
                    if text_begin == "Endless":
                        self.chat_box.setGeometry(QRect(25, 225, 350, 100))
                        self.change_status_for_conversation("hide")
                        self.chat_box.clear()
                        text_begin = "END"
                    elif text_begin == "Recover":
                        self.chat_box.setGeometry(QRect(25, 225, 350, 100))
                        self.change_status_for_conversation("show", False)
                    elif "<img" in markdown_text:
                        self.chat_box.setGeometry(QRect(0, 50, self.width(), self.height() - 125))
                        if temp_action:
                            text_begin = "Endless"
                        else:
                            text_begin = "Recover"
                        flot_timer.start(20000)
                    elif not temp_action:
                        self.change_status_for_conversation("show", False)
                    elif temp_action:
                        text_begin = "Endless"
                        flot_timer.start(3000)

            self.chat_box.clear()
            start_time = time.time()
            text_begin = -1
            is_emotion = False
            if information[0] is not None:
                SpeakThread(self, information[0]).start()

            flot_timer = QTimer(self)
            flot_timer.timeout.connect(__closure)
            flot_timer.start(5)

        common_text = text[0]
        markdown_text = __processor(text[1])

        if ((intelligence.VoiceSwitch and configure['settings']['tts']['way'] == "local") or
                configure['settings']['tts']['way'] == "cloud") and 'tts' not in configure['settings']['disable']:
            VGT = VoiceGenerateThread(self, common_text)
            VGT.result.connect(__exec)
            VGT.start()
        else:
            __exec([None, 0])

    def have_conversation(self, text: str | None = None, temp_action: bool = False):
        """进行聊天 Send conversation"""
        chat_message = str(self.conversation_entry.toPlainText()) if text is None else text
        if intelligence is None:
            return
        if not chat_message.strip():
            return
        self.conversation_button.setVisible(False)
        self.media_button.setVisible(False)
        self.clear_memories_button.setVisible(False)
        self.chat_box.setText(f"{configure['name']}思考中...\n{configure['name']} is thinking...")

        if self.image_path is None and "$[图片]$" not in self.conversation_entry.toPlainText():
            text_generate = TextGenerateThread(
                self, chat_message,
                True if "online" not in configure['settings']['disable'] else False,
            )
        else:
            text_generate = MediaUnderstandThread(
                self, self.image_path, chat_message.replace("$[图片]$", ""),
                True if "online" not in configure['settings']['disable'] else False,
            )
            self.image_path = None
        text_generate.start()
        text_generate.result.connect(lambda texts: self.conversation_display(texts, temp_action))

    def clear_memories(self):
        """清除记忆 Clear memories"""
        if intelligence is None:
            return
        intelligence.text.clear_memories()
        self.chat_box.clear()

    # 自定义事件 Custom events
    # 动画事件 Animation Event
    def finishedAnimationEvent(self):
        self.is_playing_animation = False
        self.turn_count = 0
        self.resetDefaultValueEvent()
        print("END")

    # 重置默认值事件 Reset default value event
    def resetDefaultValueEvent(self):
        for param, values in param_dict.items():
            if param == configure['watermark'].split(";")[0]:
                continue
            self.pet_model.SetParameterValue(param, values['default'], 1)

    # 事件 Events
    # 右键菜单事件 Right-click menu events
    def contextMenuEvent(self, event):
        def io_configure(value: str, relative=None, behave: object = int):
            if "{" in value and "}" in value:
                temp_dict = configure

                for key in relative.split(".")[:-1]:
                    if key not in temp_dict:
                        temp_dict[key] = {}
                    temp_dict = temp_dict[key]

                if relative.split("."):
                    last_key = relative.split(".")[-1]
                    if temp_dict[last_key]:
                        temp_dict[last_key] = 0 if behave == int else False
                    else:
                        temp_dict[last_key] = 1 if behave == int else True
            else:
                if value not in configure['settings']['disable']:
                    configure_settings['disable'].append(value)
                    if relative is not None:
                        relative()
                else:
                    configure_settings['disable'].remove(value)
                    if relative is not None:
                        relative()

            with open("./resources/configure.json", "w", encoding="utf-8") as cf:
                json.dump(configure, cf, ensure_ascii=False, indent=3)
                cf.close()

        def change_configure(relative, value):
            temp_dict = configure

            for key in relative.split(".")[:-1]:
                if key not in temp_dict:
                    temp_dict[key] = {}
                temp_dict = temp_dict[key]

            if relative.split("."):
                last_key = relative.split(".")[-1]
                temp_dict[last_key] = value

            with open("./resources/configure.json", "w", encoding="utf-8") as cf:
                json.dump(configure, cf, ensure_ascii=False, indent=3)
                cf.close()

        content_menu = QMenu(self)

        settings_action = QAction("设置 Settings", self)
        settings_action.triggered.connect(lambda: Setting().mainloop())
        content_menu.addAction(settings_action)

        content_menu.addSeparator()

        conversation_action = QAction("进行对话 Have Conversations", self)
        conversation_action.triggered.connect(self.open_close_conversation)
        content_menu.addAction(conversation_action)

        content_menu.addSeparator()

        # IO控制 IO control
        # 录屏兼容模式 Capture compatibility mode
        compatibility_action = QAction(
            f"{'√' if configure['settings']['compatibility'] else ''} 录屏兼容 Capture Compatible", self)
        compatibility_action.triggered.connect(lambda: io_configure(
            "{compatibility}", "settings.compatibility", bool))
        content_menu.addAction(compatibility_action)

        globe_mouse_penetration_action = QAction(
            f"{'√' if 'gmpene' not in configure['settings']['disable'] else ''} 全局鼠标穿透 Global Mouse Penetration", self)
        globe_mouse_penetration_action.triggered.connect(lambda: io_configure("gmpene"))
        content_menu.addAction(globe_mouse_penetration_action)

        # 语音识别 Recognition
        recognition_action = QAction(
            f"{'√' if 'rec' not in configure['settings']['disable'] else ''} 语音识别 Recognition", self)
        recognition_action.triggered.connect(lambda: io_configure("rec"))
        content_menu.addAction(recognition_action)

        # AI语音 AI voice
        ai_voice = QAction(f"{'√' if 'tts' not in configure['settings']['disable'] else ''} AI语音 AI Voice", self)
        ai_voice.triggered.connect(lambda: io_configure("tts"))
        content_menu.addAction(ai_voice)

        # 联网搜索 Online search
        online_search = QAction(
            f"{'√' if 'online' not in configure['settings']['disable'] else ''} 联网搜索 Online Search", self)
        online_search.triggered.connect(lambda: io_configure("online"))
        content_menu.addAction(online_search)

        # 翻译 Translate
        translate = QAction(f"{'√' if 'trans' not in configure['settings']['disable'] else ''} 翻译 Translate",
                            self)
        translate.triggered.connect(lambda: io_configure("trans"))
        content_menu.addAction(translate)

        # 分割线
        content_menu.addSeparator()

        # 选择菜单 Switch menu
        # 切换角色菜单 Switch character menu
        change_character_menu = QMenu("切换角色 Change Character", self)
        for index, character in enumerate(os.listdir("./resources/model")):
            character_action = QAction(
                f"{'√' if character == configure_default else ' '} {character}({configure['name']})", self)
            character_action.triggered.connect(lambda checked, c=character: change_configure("default", c))
            change_character_menu.addAction(character_action)

        content_menu.addMenu(change_character_menu)

        # 自动翻译菜单 Auto translation menu
        translation_menu = QMenu("自动翻译 Auto Trans", self)
        translation_tool_menu = QMenu("翻译工具 Trans Tools", self)

        # 爬虫翻译 Spider Translate
        translation_tool_spider_menu = QMenu(
            f"{'√' if 'spider' in configure['settings']['translate'] else ' '} 爬虫 Spider", self)
        translation_tool_spider_bing = QAction(
            f"{'√' if 'bing' in configure['settings']['translate'] else ' '} 必应 Bing", self)
        translation_tool_spider_menu.addAction(translation_tool_spider_bing)
        translation_tool_spider_bing.triggered.connect(lambda: change_configure("settings.translate", "spider.bing"))
        translation_tool_menu.addMenu(translation_tool_spider_menu)

        translation_menu.addMenu(translation_tool_menu)
        content_menu.addMenu(translation_menu)

        # AI翻译 AI Translate
        translation_tool_ai_menu = QMenu(
            f"{'√' if 'ai' in configure['settings']['translate'] else ' '} 人工智能 AI", self)
        translation_tool_ai_qwen = QAction(
            f"{'√' if 'tongyi' in configure['settings']['translate'] else ' '} 通义 Tongyi", self)
        translation_tool_ai_menu.addAction(translation_tool_ai_qwen)
        translation_tool_ai_qwen.triggered.connect(lambda: change_configure("settings.translate", "ai.tongyi"))

        translation_tool_menu.addMenu(translation_tool_ai_menu)
        content_menu.addMenu(translation_menu)

        # 语音模型切换菜单 Voice model switch menu
        voice_model_menu = QMenu("语音模型 Voice Model", self)
        for model in MODULE_INFO.keys():
            model_action = QAction(f"{'√' if model == configure['voice_model'] else ' '} {model}", self)
            model_action.triggered.connect(lambda checked, m=model: change_configure("voice_model", m))
            voice_model_menu.addAction(model_action)
        if "tts" not in configure['settings']['disable']:
            content_menu.addMenu(voice_model_menu)

        # 成人模式菜单 Adult content menu
        adult_content_menu = QMenu("成人模式 Adult Content", self)
        for level in range(configure_adults['AdultLevelMinimum'],
                           configure_adults['AdultLevelMaximum'] + 1):
            adult_content_action = QAction(
                f"{'√' if configure['adult_level'] == level else ' '} 等级 Level {level} - "
                f"{configure_adults['AdultDescribe'][str(level)]}", self)
            adult_content_menu.addAction(adult_content_action)
            adult_content_action.triggered.connect(lambda checked, lev=level: change_configure("adult_level", lev))
        if configure['adult_level']:
            content_menu.addMenu(adult_content_menu)

        exit_menu = QAction("退出 Exit", self)
        exit_menu.triggered.connect(self.exit_program)
        content_menu.addAction(exit_menu)

        content_menu.exec_(self.mapToGlobal(event.pos()))

    # 过滤器事件 Filter events
    def eventFilter(self, obj, event):
        if obj is self.conversation_entry and event.type() == event.KeyPress:
            # 是否按下 Shift + Enter When Shift + Enter is pressed
            if event.key() in (Qt.Key_Enter, Qt.Key_Return):
                if event.modifiers() & Qt.ShiftModifier and self.conversation_button.isVisible():
                    self.conversation_button.click()
                    return True
                else:
                    return False
        return super().eventFilter(obj, event)

    # 定时器事件 Timer events
    def timerEvent(self, a0: QTimerEvent | None) -> None:
        def save_change():
            self.is_penetration = False
            configure['settings']['penetration']['start'] = "next"
            configure['settings']['penetration']['enable'] = False
            with open("./resources/configure.json", "w", encoding="utf-8") as sf:
                json.dump(configure, sf, indent=3, ensure_ascii=False)
                sf.close()
            self.set_mouse_transparent(False)

        if not self.isVisible():
            return
        # 判断兼容性 Compatibility
        if configure_settings["compatibility"] is False and self.among == 100:
            # 判断顺序是否低于任务栏 Check whether the order is below the taskbar
            hwnd = self.winId().__int__()
            taskbar_hwnd = win32gui.FindWindow("Shell_TrayWnd", None)
            if win32gui.GetWindowRect(hwnd)[1] < win32gui.GetWindowRect(taskbar_hwnd)[1]:
                self.set_window_below_taskbar()

        # 检查识别器 Check the recognizer
        if not self.recognize_thread.isRunning() and "rec" not in configure['settings']['disable']:
            self.recognize()
        elif speech_rec is not None and "rec" in configure['settings']['disable']:
            speech_rec.closed()

        # 释放资源 Release resources
        # 检查说话列表的可用性 Check the availability of the speaking list
        if len(self.speaking_lists) == self.speaking_lists.count(False) and not self.speaking_lists:
            # 清除缓存 Clear empty cache
            self.speaking_lists.clear()

        # 定时器检查 Timer checker
        if "media" in configure['settings']['disable']:
            if self.look_timer.isActive():
                self.look_timer.stop()
        else:
            if not self.look_timer.isActive():
                self.look_timer.start(random.randint(
                    configure['settings']['understand']['min'],
                    configure['settings']['understand']['max']) * 1000)

        local_x, local_y = QCursor.pos().x() - self.x(), QCursor.pos().y() - self.y()
        try:
            self.pet_model.Update()
            self.pet_model.Drag(local_x, local_y)
            self.pet_model.Draw()
        except SystemError:
            pass
        # 检查是否开启全局鼠标穿透 Check whether global mouse transparency is enabled
        if configure['settings']['penetration']['enable']:
            self.set_mouse_transparent(True)
            self.is_penetration = True
            # 如果start有以下几种情况，则取消全局鼠标穿透 if start has the following four situations, cancel global mouse transparency
            # 当空的时候取消 When it is empty, cancel global mouse transparency
            if configure['settings']['penetration']['start'].strip() == "" and self.among == 0:
                save_change()
            # 下次启动时取消全局鼠标穿透 if the start is next, cancel global mouse transparency
            elif configure['settings']['penetration']['start'] == "next" and self.among == 0:
                save_change()
            # 随机取消全局鼠标穿透 if the start is random, cancel global mouse transparency
            elif configure['settings']['penetration']['start'] == 'random':
                if self.random_cancel_penetration is not None:
                    if self.random_cancel_penetration < datetime.datetime.now():
                        save_change()
                else:
                    self.random_cancel_penetration = datetime.datetime.now() + datetime.timedelta(
                        minutes=random.randint(5, 30))
            # 鼠标左键或右键在顶部按下时取消全局鼠标穿透 if the start is left-top or right-top, cancel global mouse transparency
            elif configure['settings']['penetration']['start'] in ('left-top', 'right-top'):
                if not MouseListener.isListening:
                    MouseListener.start_listening()
                if configure['settings']['penetration']['start'] == "left-top":
                    pressed = MouseListener.is_left_button_pressed
                elif configure['settings']['penetration']['start'] == "right-top":
                    pressed = MouseListener.is_right_button_pressed
                else:
                    pressed = False
                if self.is_in_live2d_area(local_x, local_y) and pressed and \
                        80 > local_y > 0:
                    MouseListener.stop_listening()
                    save_change()
            # 鼠标左键或右键在底部按下时取消全局鼠标穿透 if the start is left-bottom or right-bottom, cancel global mouse transparency
            elif configure['settings']['penetration']['start'] in ('left-bottom', 'right-bottom'):
                if not MouseListener.isListening:
                    MouseListener.start_listening()
                if configure['settings']['penetration']['start'] == "left-bottom":
                    pressed = MouseListener.is_left_button_pressed
                elif configure['settings']['penetration']['start'] == "right-bottom":
                    pressed = MouseListener.is_right_button_pressed
                else:
                    pressed = False
                if not MouseListener.isListening:
                    MouseListener.start_listening()
                if self.is_in_live2d_area(local_x, local_y) and pressed and \
                        self.height() > local_y > self.height() - 80:
                    MouseListener.stop_listening()
                    save_change()
        else:
            save_change()

        if self.among > 100:
            self.among = 0
        self.among += 1

        # 检查点击区域 Check the click area
        if self.is_in_live2d_area(local_x, local_y) and not self.is_penetration:
            self.set_mouse_transparent(False)
            self.click_in_area = True
        elif not self.is_penetration:
            self.set_mouse_transparent(True)
            self.turn_count = 0
            self.click_in_area = False

        self.update()

    def is_in_live2d_area(self, click_x, click_y):
        """检查是否在模型内 Check whether the mouse is in the model"""
        h = self.height()
        alpha = GL.glReadPixels(click_x * 1.0, (h - click_y) * 1.0, 1, 1, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)[3]
        return alpha > 0

    # 鼠标拖动事件 Mouse drag events
    def mousePressEvent(self, event):
        x, y = event.globalPos().x(), event.globalPos().y()
        if self.is_in_live2d_area(QCursor.pos().x() - self.x(), QCursor.pos().y() - self.y()):
            self.click_in_area = True
            self.click_x, self.click_y = x, y
            event.accept()

        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        def checker(parameter: str, turn_count: int) -> bool:
            """检查是否满足框内要求 Check whether the box is satisfied"""
            x_min, x_max, y_min, y_max = get_configure_actions()[parameter]['position']
            return (
                    x_min <= current_x <= x_max and y_min <= current_y <= y_max and
                    not self.is_playing_animation and self.turn_count >= turn_count and self.click_in_area
            )

        x, y = QCursor.pos().x() - self.x(), QCursor.pos().y()
        # 拖动事件 Drag events
        if event.buttons() & Qt.LeftButton:
            self.is_movement = True
            if self.drag_position is not None:
                if self.click_in_area:
                    new_pos = event.globalPos() - self.drag_position
                    new_pos.setY(max(self.screen_geometry.height() - self.height(), new_pos.y()))
                    self.move(new_pos)
                event.accept()

        # 非接触悬浮鼠标的互动 Non-touch hover mouse interaction
        if self.enter_position and not event.buttons() & Qt.LeftButton:
            # 处理互动事件/动画 Process interaction events/animation
            current_pos = event.pos()
            current_x = current_pos.x()
            current_y = current_pos.y()

            if self.last_pos is not None:
                last_x, last_y = self.last_pos.x(), self.last_pos.y()
                current_x, current_y = current_pos.x(), current_pos.y()

                # 状态 Status
                if current_x > last_x:
                    new_direction = 'right'
                elif current_x < last_x:
                    new_direction = 'left'
                else:
                    new_direction = self.direction

                # 检查方向是否改变 Check whether the direction has changed
                if self.direction is not None and new_direction != self.direction:
                    self.turn_count += 1

                self.direction = new_direction

            self.last_pos = current_pos

            if self.click_in_area and not self.is_movement:
                # 摸头互动 Touch interaction
                if checker('ActionTouchHead', 4):
                    SpeakThread(self, get_audio_path('ActionTouchHead')).start()
                    self.click_in_area = False
                    self.is_playing_animation = True
                    # 播放动画 Play animation
                    group, index = get_configure_actions()['ActionTouchHead']['motion'].split(":")
                    self.pet_model.StartMotion(group, int(index), live2d.MotionPriority.FORCE,
                                               onFinishMotionHandler=self.finishedAnimationEvent)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        def checker(parameter_action: str):
            """检查点击位置是否符合标准 Check whether the click position meets the standard"""
            x_min, x_max, y_min, y_max = get_configure_actions()[parameter_action]['position']
            return x_min <= click_x <= x_max and y_min <= click_y <= y_max \
                and not self.is_playing_animation

        click_x, click_y = event.globalPos().x() - self.x(), event.globalPos().y() - self.y()
        if event.button() == Qt.LeftButton and self.click_in_area:
            print(f"meet the requirements. CLICK pos: {click_x, click_y}")
            # 记录位置 Record position
            if configure['record']['enable_position']:
                if configure['record']['position'][:2].count(-1) == len(configure['record']['position'][:2]):
                    configure['record']['position'][:2] = [click_x, click_y]
                else:
                    configure['record']['position'][2:] = [click_x, click_y]
                    configure['record']['enable_position'] = False

            # 胸部点击行为 Chest click behavior
            if checker("ActionClickChest"):
                self.is_playing_animation = True
                group, index = get_configure_actions()['ActionClickChest']['motion'].split(":")
                self.pet_model.StartMotion(group, int(index), live2d.MotionPriority.FORCE,
                                           onFinishMotionHandler=self.finishedAnimationEvent)
                if configure['adult_level'] > 0:
                    dir_, voice_list = AdultEngine.voice()
                    SpeakThread(self,
                                f"./resources/adult/{configure['default']}/voice/{dir_}/"
                                f"{random.choice(voice_list)}").start()
                else:
                    SpeakThread(self, get_audio_path("ActionClickChest")).start()
            event.accept()
        self.is_movement = False

    # 鼠标进入事件 Mouse entry event
    def enterEvent(self, event):
        self.turn_count = 0
        self.enter_position = event.pos()

    # 鼠标离开事件 Mouse leave event
    def leaveEvent(self, event):
        self.is_movement = False
        self.enter_position = None
        self.is_playing_animation = False

    # OpenGL 事件 OpenGL events
    def initializeGL(self):
        GL.glEnable(GL.GL_DEPTH_TEST)

        live2d.glewInit()
        self.pet_model = live2d.LAppModel()
        if os.path.exists(f"./resources/model/{configure_default}/{configure_default.title()}.model3.json"):
            self.pet_model.LoadModelJson(
                f"./resources/model/{configure_default}/{configure_default.title()}.model3.json")
        else:
            self.pet_model.LoadModelJson(f"./resources/model/{configure_default}/{configure_default}.model3.json")

        for i in range(self.pet_model.GetParameterCount()):
            param = self.pet_model.GetParameter(i)
            param_dict.update({param.id: {
                "value": param.value, "max": param.max, "min": param.min, "default": param.default,
            }})
        self.startTimer(int(1000 / 900))

    def resizeGL(self, width, height):
        self.pet_model.Resize(width, height)

    def paintGL(self):
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        live2d.clearBuffer()
        # 清除水印 Clear watermark
        try:
            watermark_param = configure['watermark'].split(";")[0]
            watermark_value = configure['watermark'].split(";")[1]
            self.pet_model.SetParameterValue(
                watermark_param,
                float(watermark_value) if "." in watermark_value else int(watermark_value), 1)
        except ValueError:
            pass
        # 加载模型 Load Model
        self.pet_model.Draw()

    def exit_program(self):
        live2d.dispose()
        self.close()
        try:
            os.remove("./logs/backup/configure.json")
        except FileNotFoundError:
            pass
        shutil.copy2("./resources/configure.json", "./logs/backup/configure.json")
        logger("程序退出 Program exit", logs.HISTORY_PATH)
        os.kill(os.getpid(), __import__("signal").SIGINT)


live2d.setLogEnable(False)
live2d.init()
MouseListener = MouseListener()
AdultEngine = AdultEngine()
logger("桌宠初始化完成 Live2D初始化完成\n"
       "DesktopPet initialized successfully, Live2D initialized successfully.\n", logs.HISTORY_PATH)
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = DesktopTop()
    sys.exit(app.exec_())
