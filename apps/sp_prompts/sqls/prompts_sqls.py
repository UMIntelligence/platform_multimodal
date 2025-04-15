#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
# 类型的
PROMPTS_LIST = """select a.type_name, a.type_desc, b.prompts_name, b.prompts_desc, b.prompts_title, b.id  prompts_id
from cm_model_prompts_type a
inner join cm_model_prompts b on a.id=b.prompts_type_id
where 0=0 """


RECOMMEND_SQL = """SELECT prompts_name, id prompts_id, prompts_title from cm_model_prompts 
where p_status=1 order by uses_number desc limit 50
"""
