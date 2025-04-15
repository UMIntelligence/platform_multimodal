#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI

SpeechHistorySql = """select id, speech_code, title, audio_url, speech_text, r_status, 
DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:%s') create_time, biz_duration, r_type, file_type, file_name
from vs_speech_recognition_history as a where is_delete=0 """
