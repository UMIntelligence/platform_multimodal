#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI


EnterpriseLabelSql = """select label_code, label, label_type from ce_enterprise_label as a where is_delete=0"""

EnterpriseListSql = """select a.icon_url, a.company_code, a.company_name, a.company_desc
from ce_enterprise_info as a
inner join ce_enterprise_member as b on a.company_code=b.company_code
where b.user_code=%s and m_status=2 and b.is_delete=0
"""


EnterpriseInfoSql = """select a.company_code, a.company_name, a.company_abbreviation, a.position, a.industry_code,
a.registered_address, a.company_desc, a.company_url, a.ipc_code, a.company_mobile, a.company_mailbox,
a.company_address, a.status, b.label
from ce_enterprise_info a
left join ce_enterprise_label b on a.industry_code=b.label_code and b.label_type=1
where a.company_code=%s
"""

ProjectInfoSql = """select company_code, project_code, category_name, project_name, brief_introduction
from ce_enterprise_project_info 
where company_code=%s and is_delete=0"""


InformationInfoSql = """select a.company_code, a.information_code, a.label_code, a.information_name, a.content_desc,
b.label
from ce_enterprise_information_info as a
left join ce_enterprise_label b on a.label_code=b.label_code and b.label_type=2
where a.company_code=%s and a.is_delete=0"""


KnowledgeSql = """select b.label, a.company_code, a.knowledge_code, a.category, a.content_desc, a.purpose, 
a.category_name, a.title
from ce_enterprise_knowledge_base as a
left join ce_enterprise_label b on a.category=b.label_code and b.label_type=3
where a.company_code=%s and a.is_delete=0"""


EnterpriseMemberSql = """select a.member_code, a.m_status, b.nick_name, b.avatar_url, b.mobile,
DATE_FORMAT(a.create_time, '%Y-%m-%d %H:%i:%s') create_time
from ce_enterprise_member as a
inner join uu_users as b on a.user_code=b.user_code
where a.is_delete=0 """

EnterpriseDigitalClerkSql = """select clerk_code, company_code, knowledge_code, clerk_name, icon_url, welcome_msg,
DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:%s') create_time, d_status
from ce_enterprise_digital_clerk as a
where is_delete=0 """


KnowledgeListSql = """select a.company_code, a.knowledge_code, b.nick_name, b.mobile,
DATE_FORMAT(a.create_time, '%Y-%m-%d %H:%i:%s') create_time, a.title
from ce_enterprise_knowledge_base as a
inner join uu_users as b on a.create_by=b.user_code
where a.is_delete=0 """