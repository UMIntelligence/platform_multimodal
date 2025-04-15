#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI


SpeechList = """select h_code, engine_code, voice_code, title, speech_url, 
DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:%s') create_time
from vt_text_to_speech_history where is_delete=0 and h_status=2"""


SpeechDtl = """select a.h_code, a.engine_code, a.voice_code, a.title, a.speech_url, 
DATE_FORMAT(a.create_time, '%%Y-%%m-%%d %%H:%%i:%%s') create_time, b.engine_name, b.model, c.voice,
c.voice_name, c.voice_logo, c.speech_url c_speech_url, a.content, a.language, a.task_id, a.h_status,
a.speech_rate, a.pitch_rate
from vt_text_to_speech_history a
inner join vt_text_to_speech_engine b on a.engine_code=b.engine_code
inner join vt_text_to_speech_voice c on a.voice_code=c.voice_code
where a.h_code=%s"""
