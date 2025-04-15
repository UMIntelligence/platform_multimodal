#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI


DigitalHumanFileSql = """select file_code, file_url, f_type, DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:%s') create_time,
file_name, file_type 
from vd_digital_human_file as a where is_delete=0"""

# 数字人形象列表
MyDigitalHumanSql = """select live_code, live_name, live_video_url, live_video_code, power_attorney_url,
make_status, live_type, DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:%s') create_time, video_cover_url
from vd_digital_human_live_video where live_type=0 and is_delete=0
union all 
select live_code, live_name, live_video_url, live_video_code, power_attorney_url,
make_status, live_type, DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:%s') create_time, video_cover_url
from vd_digital_human_live_video where live_type=1 and is_delete=0"""

# 口播视频项目列表
DigitalHumanProjectSql = """
select a.video_cover_url, a.live_video_url, a.live_code, b.project_code,
b.project_name, b.project_status, DATE_FORMAT(b.create_time, '%Y-%m-%d %H:%i:%s') create_time
from vd_digital_human_project as b
inner join vd_digital_human_live_video as a on a.live_code=b.live_code
where a.is_delete=0 and b.is_delete=0
"""

MyLiveVideoSql = """select c.project_code, c.video_name,  c.complete_url, c.make_status,
a.video_cover_url, DATE_FORMAT(c.create_time, '%Y-%m-%d %H:%i:%s') create_time, c.live_dtl_code
from vd_digital_human_live_video a
inner join vd_digital_human_project b on a.live_code=b.live_code
inner join vd_digital_human_live_video_dtl c on b.project_code=c.project_code
where a.make_status = 0 and b.project_status =0"""    #  c.make_status != 1

HumanProjectDtl = """select a.video_cover_url, a.live_video_url, a.live_code, b.project_code,
b.project_name, b.project_status, b.create_by, b.v_type, b.sound_type, b.voice_code, c.voice_name
from vd_digital_human_project as b
inner join vd_digital_human_live_video as a on a.live_code=b.live_code
left join vt_text_to_speech_voice as c on b.voice_code=c.voice_code
where b.create_by=%s and b.project_code=%s
"""

# 获取任务a.make_status=0 and c.project_status=0两个都支付成功
GetListMakeSql = """select b.id, a.live_code, a.live_video_url, a.live_video_code, b.live_dtl_code, b.create_by, 
    b.live_sound_url, b.complete_url, b.make_status, c.v_type, c.sound_type, b.live_script, c.voice_code 
    from vd_digital_human_live_video as a
    inner join vd_digital_human_project as c on a.live_code=c.live_code
    inner join vd_digital_human_live_video_dtl as b on c.project_code=b.project_code
    where a.make_status=0 and c.project_status=0 and b.make_status=1
    order by b.id asc
    LIMIT 1"""


CustomizedVoiceSql = """select voice_name, voice_code, gender, scenario, voice_status, voice_type, reason, model_id,
DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:%s') create_time, create_by, id
from vd_digital_human_customized_voice as a
where 0=0 """


VoiceGenerateHistorySql = """select voice_code, h_code, live_sound_url, live_script, h_status, h_type, reason,
DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:%s') create_time, create_by
from vd_digital_human_voice_generate_history as a
where 0=0 """
