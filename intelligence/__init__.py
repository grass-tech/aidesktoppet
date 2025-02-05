from . import text
from . import recognition

VoiceSwitch = True
try:
    from . import voice
    from . import translate
except ImportError:
    VoiceSwitch = False

ALI_API_KEY = ""
XF_API_ID = ""
XF_API_KEY = ""
XF_API_SECRET = ""


def xf_speech_recognition(success_func, error_func, close_func):
    recognition.API_ID = XF_API_ID
    recognition.API_KEY = XF_API_KEY
    recognition.API_SECRET = XF_API_SECRET
    return recognition.XFRealTimeSpeechRecognizer(success_func, error_func, close_func)


def whisper_speech_recognition(success_func, error_func, close_func, url):
    return recognition.WhisperRealTimeSpeechRecognizer(url, success_func, error_func, close_func)


def text_generator(prompt, is_search_online: bool):
    a = text.TextGenerator(ALI_API_KEY).generate_text(prompt, is_search_online)
    return a


def gsv_voice_generator(texts, language, module_name, module_info, top_k=12, top_p=0.95, temperature=0.34, speed=1.0,
                        batch_size=3, batch_threshold=0.75, seed=-1, parallel_infer=True, repetition_penalty=1.35,
                        url=None):
    return voice.take_a_tts(texts, language, module_name, module_info,
                            top_k, top_p, temperature, speed, batch_size, batch_threshold,
                            seed, parallel_infer, repetition_penalty)


def ali_voice_generator(texts):
    return voice.ali_tts(texts, ALI_API_KEY)


def voice_change(name, modules):
    return voice.change_module(name, modules)


def machine_translate(prompt):
    return translate.machine_translate(prompt)


def tongyi_translate(words):
    return translate.tongyi_translate(words, ALI_API_KEY)
