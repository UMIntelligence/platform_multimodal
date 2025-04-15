#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI


TRAIN_HISTORY = """select a.train_code, a.voice_id, a.voice_name, a.voice_status, a.voice_type, a.remark, 
a.demo_audio, a.audios, DATE_FORMAT(a.create_time, '%Y-%m-%d %H:%i:%s') create_time, b.voice_code, b.engine_code
from vt_voice_train_history a
left join vt_text_to_speech_voice b on a.voice_id=b.voice and b.create_by='{}'
where a.is_delete=0"""
