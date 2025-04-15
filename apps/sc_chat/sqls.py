#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
# chat gpt 会话列表 CASE chat_type WHEN 0 THEN 'GPT35' WHEN 1 THEN 'GPT40' WHEN 2 THEN 'DALL·E 2' WHEN 3 THEN '百度绘画'
#     WHEN 4 THEN '百度绘画'
#     ELSE 'mj' END chat_type_name,
CHAT_LIST_SQL = """select a.session_code, title, chat_type, a.create_by,  question_id, a.model,
DATE_FORMAT(a.create_time, '%Y-%m-%d %H:%i:%s') create_time, b.clerk_code, b.company_code, c.nick_name, a.scenario_type
    from cc_chat_session a 
    left join uu_users c on a.create_by=c.user_code
    left join cd_digital_clerk_chat b on a.session_code=b.session_code
    where a.is_delete=0"""


IMAGE_LIST_SQL = """SELECT s.session_code, title, chat_type, 
DATE_FORMAT(s.create_time, '%Y-%m-%d %H:%i:%s') create_time, d.content, d.status, d.is_mod
FROM cc_chat_session s
JOIN (
  SELECT session_code, MAX(id) AS min_id
  FROM cc_chat_session_dtl where is_delete=0 
  GROUP BY session_code
) AS d_min ON s.session_code = d_min.session_code
JOIN cc_chat_session_dtl d ON d_min.session_code = d.session_code AND d_min.min_id = d.id
where s.is_delete=0 and d.is_delete = 0 and chat_type in (2,3,6,9, -1) and d.is_mod != 1 and d.status != 1"""


# -----------------------图片
IMAGE_LIST_SQL2 = """select a.image_code, title, chat_type, a.model, a.action_type, a.source,
DATE_FORMAT(a.create_time, '%Y-%m-%d %H:%i:%s') create_time, b.msg_code, b.result_image, b.origin_image
    from cc_chat_image a 
    inner join cc_chat_image_dtl b on a.image_code=b.image_code
    where a.is_delete=0 and b.is_delete=0 and b.role='assistant' and b.is_mod != 1 and b.status != 1"""

IMAGE_DTL_SQL = """select b.image_code,  a.chat_type, b.is_likes, b.msg_code, b.style, a.model,
    DATE_FORMAT(b.create_time, '%%Y-%%m-%%d %%H:%%i:%%s') create_time, role, action_type, b.size, b.covert_prompt,
    b.id image_dtl_id, b.integral, b.is_mod, b.status,b.task_id, b.prompt, b.negative_prompt, b.origin_image, 
    b.result_image, b.quality, b.result_list, b.change_degree, b.refer_image, b.progress, b.sampler_index, b.seed,
    b.steps, b.cfg_scale, b.prompt_en, b.negative_prompt_en, b.origin_image
    from cc_chat_image a
    inner join cc_chat_image_dtl b on a.image_code=b.image_code
    where b.image_code= %s and b.create_by = %s and a.is_delete=0 and b.is_delete=0"""

# 正式用户
CHAT_RETRIEVE_SQL = """select b.session_code, chat_group_code, finish_reason, a.chat_type, b.is_likes, b.msg_code,
    DATE_FORMAT(b.create_time, '%%Y-%%m-%%d %%H:%%i:%%s') create_time, role, content, action_type, b.size, 
    b.id session_dtl_id, b.integral, b.total_tokens, b.completion_tokens, b.prompt_tokens, a.question_id, b.images,
    b.covert_content, b.is_mod, b.status,b.task_id, a.model, b.audio_url
    from cc_chat_session a
    inner join cc_chat_session_dtl b on a.session_code=b.session_code
    where b.session_code= %s and b.create_by = %s and a.is_delete=0 and b.is_delete=0;"""


CHAT_SQUARE = """select b.session_data, a.session_code 
from cc_chat_square a
inner join cc_chat_messages b on a.session_code=b.session_code
where a.s_status =2 """


CHAT_SQUARE_RAND = """SELECT DISTINCT b.session_data, t1.session_code, t1.id 
FROM cc_chat_square AS t1 
join  cc_chat_messages b ON t1.session_code=b.session_code
where t1.s_status = 2 and t1.is_delete=0 and t1.module_id = %s and t1.question_id = %s
LIMIT 300;"""


QuestionSql = """select question_id, character_avatar, character_name, character_greetings
from uqd_user_question_details where 0=0 """


# --------------------------------------------多模型-----------------
ChatRoleList = """select role_code, role_name, role_logo, chat_type, model, covert_content, role_type,
DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:%s') create_time, create_by
from cg_chat_role where is_delete=0 and role_type=1
UNION ALL
select role_code, role_name, role_logo, chat_type, model, covert_content, role_type,
DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:%s') create_time, create_by
from cg_chat_role where is_delete=0 and role_type=2 
"""

GroupChatList = """select session_code, title, subject, use_integral, total_integral,
DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:%s') create_time
from cg_group_chat where is_delete=0"""


GroupChatDtl = """select a.session_code, a.msg_code, a.chat_type, a.model, a.role, a.content, a.covert_content,
a.integral, a.is_likes, c.role_code, c.role_name, c.role_logo, a.group_role_code 
from cg_group_chat_dtl as a
left join cg_group_chat_role b on a.group_role_code=b.group_role_code
left join cg_chat_role c on b.role_code=c.role_code
where a.session_code=%s  """    # and not (a.group_role_code != '' and a.role='user')

# group_chat_role
GroupChatRole = """select a.group_role_code, a.role_code, b.chat_type, b.model, b.covert_content, b.role_logo,
b.role_name
from cg_group_chat_role a
inner join  cg_chat_role b on a.role_code=b.role_code
where a.session_code=%s
order by sort_no"""
