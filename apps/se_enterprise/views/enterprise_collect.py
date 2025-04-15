#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.db import transaction, connections
from django.db.models import F
from rest_framework.decorators import action
from rest_framework.viewsets import ViewSet

from apps.se_enterprise.models.enterprise_models import CeEnterpriseInfo, CeEnterpriseProjectInfo, \
    CeEnterpriseInformationInfo, CeEnterpriseKnowledgeBase, CeEnterpriseFiles, CeEnterpriseMember, \
    CeEnterpriseDigitalClerk
from apps.se_enterprise.sqls import enterprise_sqls
from language.language_pack import RET
from se_enterprise.serializers.enterprise_serializers import EnterpriseMemberSerializer, \
    EnterpriseDigitalClerkSerializer
from utils import constants
from utils.cst_class import CstResponse, CstException
from utils.generate_number import set_flow
from utils.generics import TyModelViewSet
from utils.model_save_data import ModelSaveData
from utils.mq_utils import RabbitMqUtil
from utils.sql_utils import NewSqlMixin, dict_fetchall

applet = "applet"
official_account = "official_account"
company_log = "company_log"
company_image = "company_image"
file_code = "file"
image_code = "image"
vlog_code = "vlog"
website_code = "website"
project_image = "project_image"     # 项目产品类型
information_image = "information_image"     # 资讯产品类型


class EnterpriseInfo(ViewSet):
    """
    企业营销资产视图 作者：xiaotao 版本号: 文档地址:
    """
    model_filter = ModelSaveData()

    @staticmethod
    def get_file_values(code, file_category=constants.FILE_E_CATEGORY, group_code=""):
        return CeEnterpriseFiles.objects.filter(
            code=code, file_category=file_category, group_code=group_code
        ).annotate(name=F("file_name")).values("id", "file_url", "group_code", "file_category", "file_name", "name")

    def list(self, request, *args, **kwargs):
        user_code = request.user.user_code
        with connections["default"].cursor() as cursor:
            cursor.execute(enterprise_sqls.EnterpriseListSql, [user_code])
            rows = dict_fetchall(cursor)
        return CstResponse(RET.OK, data=rows)

    def retrieve(self, request, *args, **kwargs):
        user_code = request.user.user_code
        company_code = request.query_params.get("company_code")
        if not company_code:
            return CstResponse(RET.DATE_ERROR)
        with connections["default"].cursor() as cursor:
            cursor.execute(enterprise_sqls.EnterpriseInfoSql, [company_code])
            rows = dict_fetchall(cursor)
            if not rows:
                return CstResponse(RET.OK, data={})
            row = rows[0]

            row["company_applet_list"] = self.get_file_values(company_code, constants.FILE_E_CATEGORY, applet)
            row["company_official_account_list"] = self.get_file_values(company_code, constants.FILE_E_CATEGORY, official_account)
            row["company_log_list"] = self.get_file_values(company_code, constants.FILE_E_CATEGORY, company_log)
            row["company_image_list"] = self.get_file_values(company_code, constants.FILE_E_CATEGORY, company_image)
            self.reverse_property(row, company_code)

            # 项目信息
            cursor.execute(enterprise_sqls.ProjectInfoSql, [company_code])
            project_rows = dict_fetchall(cursor)
            for project in project_rows:
                project_code = project["project_code"]
                project["project_image_list"] = self.get_file_values(project_code, constants.FILE_P_CATEGORY, project_image)

                self.reverse_property(project, project_code, file_category=constants.FILE_P_CATEGORY)
            row["project_list"] = project_rows

            # 资讯信息
            cursor.execute(enterprise_sqls.InformationInfoSql, [company_code])
            information_rows = dict_fetchall(cursor)
            for information in information_rows:
                information_code = information["information_code"]
                information["information_image_list"] = self.get_file_values(information_code, constants.FILE_I_CATEGORY, information_image)

                self.reverse_property(information, information_code, file_category=constants.FILE_I_CATEGORY)
            row["information_list"] = information_rows

            # 知识库
            cursor.execute(enterprise_sqls.KnowledgeSql, [company_code])
            knowledge_rows = dict_fetchall(cursor)
            for knowledge in knowledge_rows:
                knowledge_code = knowledge["knowledge_code"]
                self.reverse_property(knowledge, knowledge_code, file_category=constants.FILE_K_CATEGORY)
            row["knowledge_list"] = knowledge_rows

        return CstResponse(RET.OK, data=row)

    def company_update(self, request, *args, **kwargs):
        """修改企业信息"""
        data = request.data
        company_code = data.get("company_code")
        if not company_code:
            return CstResponse(RET.DATE_ERROR)
        enterprise_save = self.model_filter.get_request_save_data(data, CeEnterpriseInfo, exclude=["company_code"])
        CeEnterpriseInfo.objects.filter(company_code=company_code).update(
            **enterprise_save
        )
        return CstResponse(RET.OK)

    def company_create_or_update(self, request, *args, **kwargs):
        """修改或创建企业信息"""
        data = request.data
        user_code = request.user.user_code
        company_code = data.get("company_code")
        # action = data.get("action")
        # if not action or action not in ["save", "submit"]:
        #     return CstResponse(RET.DATE_ERROR)

        enterprise_save = self.model_filter.get_request_save_data(data, CeEnterpriseInfo, exclude=["company_code"])

        enterprise_save["create_by"] = user_code
        # if action == "save":
        #     enterprise_save["status"] = constants.ENTERPRISE_SAVE
        # else:
        enterprise_save["status"] = constants.ENTERPRISE_SUBMIT
        if company_code:    # 修改
            if not CeEnterpriseInfo.objects.filter(company_code=company_code, status=constants.ENTERPRISE_SUBMIT).exists():
                return CstResponse(RET.NO_DATE_ERROR)
            self.update_company(company_code, data, enterprise_save)
        else:               # 创建
            # if CeEnterpriseInfo.objects.filter(create_by=user_code, status=constants.ENTERPRISE_SUBMIT).exists():
            #     return CstResponse(RET.DATE_ERROR, "已经创建过了，请勿重复创建")
            company_code = self.create_company(data, enterprise_save)

        return CstResponse(RET.OK, data=company_code)

    def project_create_or_update(self, request, *args, **kwargs):
        """修改或创建项目信息"""
        data = request.data
        user_code = request.user.user_code
        company_code = data.get("company_code")  # 企业id
        project_list = data.get("project_list") or []  # 项目列表

        obj = CeEnterpriseInfo.objects.filter(company_code=company_code).first()
        if not obj:
            return CstResponse(RET.NO_DATE_ERROR, "请先填写企业信息")

        project_codes = [i["project_code"] for i in CeEnterpriseProjectInfo.objects.filter(company_code=company_code).values("project_code")]

        with transaction.atomic():
            insert_list = []
            for project_dict in project_list:
                file_list = project_dict.get("file_list") or []  # 资料文件
                image_list = project_dict.get("image_list") or []  # 资料图片
                vlog_list = project_dict.get("vlog_list") or []  # 资料视频
                website_list = project_dict.get("website_list") or []  # 资料网址
                project = self.model_filter.get_request_save_data(project_dict, CeEnterpriseProjectInfo)

                try:
                    project_code = project.pop("project_code")
                except KeyError as e:
                    project_code = ""
                if project_code:
                    project_codes.remove(project_code)
                    CeEnterpriseProjectInfo.objects.filter(project_code=project_code).update(**project)
                else:
                    project_code = set_flow()
                    project["company_code"] = company_code
                    project["project_code"] = project_code
                    project["create_by"] = user_code
                    insert_list.append(CeEnterpriseProjectInfo(**project))

                project_image_list = project_dict.get("project_image_list") or []
                project_image_ids = [i["id"] for i in CeEnterpriseFiles.objects.filter(
                    code=project_code, group_code=project_image, file_category=constants.FILE_P_CATEGORY).values("id")]
                self.create_or_update_file(
                    project_code, project_image_list, project_image_ids, file_category=constants.FILE_P_CATEGORY,
                    group_code=project_image)
                self.update_property(project_code, file_list, image_list, vlog_list, website_list,
                                     file_category=constants.FILE_P_CATEGORY)
            CeEnterpriseProjectInfo.objects.bulk_create(insert_list)
            CeEnterpriseProjectInfo.objects.filter(project_code__in=project_codes).delete()
            CeEnterpriseFiles.objects.filter(code__in=project_codes, file_category=constants.FILE_P_CATEGORY).delete()

        return CstResponse(RET.OK)

    def information_create_or_update(self, request, *args, **kwargs):
        """资讯信息"""
        data = request.data
        user_code = request.user.user_code
        company_code = data.get("company_code")  # 企业id
        information_list = data.get("information_list") or []  # 项目列表

        obj = CeEnterpriseInfo.objects.filter(company_code=company_code).first()
        if not obj:
            return CstResponse(RET.NO_DATE_ERROR, "请先填写企业信息")

        information_codes = [i["information_code"] for i in CeEnterpriseInformationInfo.objects.filter(
            company_code=company_code).values("information_code")]

        with transaction.atomic():
            insert_list = []
            for information_dict in information_list:
                file_list = information_dict.get("file_list") or []  # 资料文件
                image_list = information_dict.get("image_list") or []  # 资料图片
                vlog_list = information_dict.get("vlog_list") or []  # 资料视频
                website_list = information_dict.get("website_list") or []  # 资料网址
                information = self.model_filter.get_request_save_data(information_dict, CeEnterpriseInformationInfo)
                try:
                    information_code = information.pop("information_code")
                except KeyError as e:
                    information_code = ""
                if information_code:
                    information_codes.remove(information_code)
                    CeEnterpriseInformationInfo.objects.filter(information_code=information_code).update(**information)
                else:
                    information_code = set_flow()
                    information["information_code"] = information_code
                    information["create_by"] = user_code
                    information["company_code"] = company_code
                    insert_list.append(CeEnterpriseInformationInfo(**information))

                information_image_list = information_dict.get("information_image_list") or []
                project_image_ids = [i["id"] for i in CeEnterpriseFiles.objects.filter(
                    code=information_code, group_code=information_image, file_category=constants.FILE_I_CATEGORY).values("id")]
                self.create_or_update_file(
                    information_code, information_image_list, project_image_ids, file_category=constants.FILE_I_CATEGORY,
                    group_code=information_image)

                self.update_property(information_code, file_list, image_list, vlog_list, website_list,
                                     file_category=constants.FILE_I_CATEGORY)
            CeEnterpriseInformationInfo.objects.bulk_create(insert_list)
            CeEnterpriseInformationInfo.objects.filter(information_code__in=information_codes).delete()
            CeEnterpriseFiles.objects.filter(code__in=information_codes, file_category=constants.FILE_I_CATEGORY).delete()

        return CstResponse(RET.OK)

    def knowledge_create_or_update(self, request, *args, **kwargs):
        """知识库"""
        data = request.data
        user_code = request.user.user_code
        company_code = data.get("company_code")  # 企业id
        knowledge_list = data.get("knowledge_list") or []  # 知识库列表

        obj = CeEnterpriseInfo.objects.filter(company_code=company_code).first()
        if not obj:
            return CstResponse(RET.NO_DATE_ERROR, "请先填写企业信息")

        knowledge_codes = [i["knowledge_code"] for i in CeEnterpriseKnowledgeBase.objects.filter(
            company_code=company_code).values("knowledge_code")]

        rabbit_mq = RabbitMqUtil()
        mq_list = []
        with transaction.atomic():
            insert_list = []
            for knowledge in knowledge_list:
                save_knowledge = self.model_filter.get_request_save_data(knowledge, CeEnterpriseKnowledgeBase)
                try:
                    knowledge_code = save_knowledge.pop("knowledge_code")
                except KeyError as e:
                    knowledge_code = ""
                if knowledge_code:
                    knowledge_codes.remove(knowledge_code)
                    CeEnterpriseKnowledgeBase.objects.filter(knowledge_code=knowledge_code).update(**save_knowledge)
                    # 修改时,如果存在绑定的数字员工需要重新训练
                    c_query = CeEnterpriseDigitalClerk.objects.filter(company_code=company_code,
                                                                      knowledge_code=knowledge_code).all()
                    for c_obj in c_query:
                        mq_data = {
                            'exchange': "digital_clerk_exchange",
                            'queue': "digital_clerk_query",
                            'routing_key': 'DigitalClerk',
                            'type': "direct",
                            "msg": {
                                "clerk_code": c_obj.clerk_code,
                                "company_code": c_obj.company_code,
                                "knowledge_code": c_obj.knowledge_code,
                            }
                        }

                        mq_list.append(mq_data)
                else:
                    knowledge_code = set_flow()
                    save_knowledge["knowledge_code"] = knowledge_code
                    save_knowledge["company_code"] = company_code
                    save_knowledge["create_by"] = user_code
                    insert_list.append(CeEnterpriseKnowledgeBase(**save_knowledge))

                file_list = knowledge.get("file_list") or []  # 资料文件
                image_list = knowledge.get("image_list") or []  # 资料图片
                vlog_list = knowledge.get("vlog_list") or []  # 资料视频
                website_list = knowledge.get("website_list") or []  # 资料网址
                self.update_property(
                    knowledge_code, file_list, image_list, vlog_list, website_list, file_category=constants.FILE_K_CATEGORY)
            CeEnterpriseKnowledgeBase.objects.bulk_create(insert_list)
            CeEnterpriseKnowledgeBase.objects.filter(knowledge_code__in=knowledge_codes).delete()
            CeEnterpriseFiles.objects.filter(code__in=knowledge_codes, file_category=constants.FILE_K_CATEGORY).delete()
            CeEnterpriseDigitalClerk.objects.filter(company_code=company_code, knowledge_code__in=knowledge_codes).delete()

            for m in mq_list:
                rabbit_mq.send_handle(m)
        return CstResponse(RET.OK)

    def update_company(self, company_code, data, enterprise_save):
        company_applet_list = data.get("company_applet_list") or []     # 公司小程序
        company_official_account_list = data.get("company_official_account_list") or []  # 公司公众号
        company_log_list = data.get("company_log_list") or []  # 公司log
        company_image_list = data.get("company_image_list") or []  # 公司图片

        file_list = data.get("file_list") or []  # 资料文件
        image_list = data.get("image_list") or []  # 资料图片
        vlog_list = data.get("vlog_list") or []  # 资料视频
        website_list = data.get("website_list") or []  # 资料网址

        applet_ids = [i["id"] for i in CeEnterpriseFiles.objects.filter(
            code=company_code, group_code=applet, file_category=constants.FILE_E_CATEGORY).values("id")]
        account_ids = [i["id"] for i in CeEnterpriseFiles.objects.filter(
            code=company_code, group_code=official_account, file_category=constants.FILE_E_CATEGORY).values("id")]
        log_ids = [i["id"] for i in CeEnterpriseFiles.objects.filter(
            code=company_code, group_code=company_log, file_category=constants.FILE_E_CATEGORY).values("id")]
        company_image_ids = [i["id"] for i in CeEnterpriseFiles.objects.filter(
            code=company_code, group_code=company_image, file_category=constants.FILE_E_CATEGORY).values("id")]

        with transaction.atomic():
            CeEnterpriseInfo.objects.filter(company_code=company_code, status=constants.ENTERPRISE_SUBMIT).update(
                **enterprise_save
            )
            self.create_or_update_file(company_code, company_applet_list, applet_ids, group_code=applet)       # 小程序
            self.create_or_update_file(company_code, company_official_account_list, account_ids, group_code=official_account)       # 公众号
            self.create_or_update_file(company_code, company_log_list, log_ids, group_code=company_log)       # 公司log
            self.create_or_update_file(company_code, company_image_list, company_image_ids, group_code=company_image)   # 公司图片

            self.update_property(company_code, file_list, image_list, vlog_list, website_list)

        return CstResponse(RET.OK)

    def create_company(self, data, enterprise_save):
        company_applet_list = data.get("company_applet_list") or []     # 公司小程序
        company_official_account_list = data.get("company_official_account_list") or []  # 公司公众号
        company_log_list = data.get("company_log_list") or []  # 公司log
        company_image_list = data.get("company_image_list") or []  # 公司图片

        file_list = data.get("file_list") or []  # 资料文件
        image_list = data.get("image_list") or []  # 资料图片
        vlog_list = data.get("vlog_list") or []  # 资料视频
        website_list = data.get("website_list") or []  # 资料网址

        company_code = set_flow()
        enterprise_save["company_code"] = company_code

        with transaction.atomic():
            CeEnterpriseInfo.objects.create(**enterprise_save)  # 企业信息
            self.create_file(company_applet_list, company_code, group_code=applet)
            self.create_file(company_official_account_list, company_code, group_code=official_account)
            self.create_file(company_log_list, company_code, group_code=company_log)
            self.create_file(company_image_list, company_code, group_code=company_image)

            self.save_property(company_code, file_list, image_list, vlog_list, website_list)

            CeEnterpriseMember.objects.create(
                member_code=set_flow(),
                company_code=company_code,
                user_code=enterprise_save["create_by"],
                m_status=2,
            )

        return company_code

    def create_file(self, file_list, code, model=CeEnterpriseFiles, is_save=1, file_category=constants.FILE_E_CATEGORY, group_code=""):
        insert_list = []
        save_list = self.model_filter.get_request_save_data(file_list, model)
        for i in save_list:
            i["code"] = code
            i["file_category"] = file_category
            i["group_code"] = group_code
            insert_list.append(model(**i))
        if is_save == 1:
            model.objects.bulk_create(insert_list)
            return []
        else:
            return insert_list

    def create_or_update_file(self, code, file_list, file_ids, file_category=constants.FILE_E_CATEGORY, group_code=""):
        file_save_list = self.model_filter.get_request_save_data(file_list, CeEnterpriseFiles, exclude=["code"])

        insert_file = []
        for file in file_save_list:
            try:
                applet_id = file.pop("id")
            except KeyError as e:
                applet_id = 0
            if applet_id:  # 修改
                file_ids.remove(applet_id)
                CeEnterpriseFiles.objects.filter(id=applet_id).update(**file)
            else:
                file["code"] = code
                file["file_category"] = file_category
                file["group_code"] = group_code
                insert_file.append(CeEnterpriseFiles(**file))
        CeEnterpriseFiles.objects.bulk_create(insert_file)  # 新增
        CeEnterpriseFiles.objects.filter(id__in=file_ids).delete()  # 删除

    def save_property(self, code, file_list, image_list, vlog_list, website_list, file_category=constants.FILE_E_CATEGORY):
        self.create_file(file_list, code, file_category=file_category, group_code=file_code)
        self.create_file(image_list, code, file_category=file_category, group_code=image_code)
        self.create_file(vlog_list, code, file_category=file_category, group_code=vlog_code)
        self.create_file(website_list, code, file_category=file_category, group_code=website_code)

    def update_property(self, code, file_list, image_list, vlog_list, website_list, file_category=constants.FILE_E_CATEGORY):
        file_ids = [i["id"] for i in CeEnterpriseFiles.objects.filter(
            code=code, group_code=file_code, file_category=file_category).values("id")]
        self.create_or_update_file(code, file_list, file_ids, file_category=file_category, group_code=file_code)

        image_ids = [i["id"] for i in CeEnterpriseFiles.objects.filter(
            code=code, group_code=image_code, file_category=file_category).values("id")]
        self.create_or_update_file(code, image_list, image_ids, file_category=file_category, group_code=image_code)

        vlog_ids = [i["id"] for i in CeEnterpriseFiles.objects.filter(
            code=code, group_code=vlog_code, file_category=file_category).values("id")]
        self.create_or_update_file(code, vlog_list, vlog_ids, file_category=file_category, group_code=vlog_code)

        website_ids = [i["id"] for i in CeEnterpriseFiles.objects.filter(
            code=code, group_code=website_code, file_category=file_category).values("id")]
        self.create_or_update_file(code, website_list, website_ids, file_category=file_category, group_code=website_code)

    def reverse_property(self, row, company_code, file_category=constants.FILE_E_CATEGORY):
        row["file_list"] = self.get_file_values(company_code, file_category, file_code)
        row["image_list"] = self.get_file_values(company_code, file_category, image_code)
        row["vlog_list"] = self.get_file_values(company_code, file_category, vlog_code)
        row["website_list"] = self.get_file_values(company_code, file_category, website_code)


class KnowledgeView(NewSqlMixin, TyModelViewSet):
    """
    知识库列表
    """
    query_sql = enterprise_sqls.KnowledgeListSql
    sort_field = ["a__create_time"]
    where = " and "
    queryset = CeEnterpriseKnowledgeBase.objects.filter(is_delete=0)
    lookup_field = "knowledge_code"

    def set_query_sql(self):
        company_code = self.request.query_params.get('company_code')
        title = self.request.query_params.get('title')
        nice_name = self.request.query_params.get('nice_name')
        mobile = self.request.query_params.get('mobile')
        if not company_code:
            raise CstException(RET.DATE_ERROR)
        self.query_sql += f" and a.company_code = {company_code}"
        if title:
            self.query_sql += f" and a.title like '{title}%'"
        if nice_name:
            self.query_sql += f" and b.nice_name = {nice_name}"
        if mobile:
            self.query_sql += f" and b.mobile = {mobile}"
        return self.query_sql

    def list(self, request, *args, **kwargs):
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        return CstResponse(RET.OK, data={'total': total, 'data': rows})

    def perform_destroy(self, instance):
        with transaction.atomic():
            CeEnterpriseFiles.objects.filter(code__in=instance.knowledge_code, file_category=constants.FILE_K_CATEGORY).delete()
            CeEnterpriseDigitalClerk.objects.filter(company_code=instance.company_code,
                                                    knowledge_code=instance.knowledge_code).delete()
            instance.delete()


class EnterpriseLabel(ViewSet, NewSqlMixin):
    """
    标签
    """
    query_sql = enterprise_sqls.EnterpriseLabelSql
    sort_field = ["create_time"]
    main_table = "a"
    where = " and "

    def set_query_sql(self):
        label_type = self.request.query_params.get('label_type')
        if label_type:
            self.query_sql += f" and label_type = {label_type}"
        return self.query_sql

    def list(self, request, *args, **kwarg):
        """
        会话框列表视图
        :param request:
        :param args:
        :param kwarg:
        :return:
        """
        label_type = self.request.query_params.get('label_type')
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        if not label_type:
            resp = {
                "industry": [],
                "information": [],
                "category": [],
            }
            for i in rows:
                if i["label_type"] == 1:
                    resp["industry"].append(i)
                elif i["label_type"] == 2:
                    resp["information"].append(i)
                else:
                    resp["category"].append(i)
            return CstResponse(RET.OK, data=resp)
        return CstResponse(RET.OK, data={'total': total, 'data': rows})


class EnterpriseMemberView(TyModelViewSet, NewSqlMixin):
    """
    企业成员视图 作者：xiaotao 版本号: 文档地址:
    """
    query_sql = enterprise_sqls.EnterpriseMemberSql
    sort_field = ["create_time"]
    main_table = "a"
    where = " and "
    queryset = CeEnterpriseMember.objects.filter(is_delete=0)
    serializer_class = EnterpriseMemberSerializer
    lookup_field = "member_code"

    def set_query_sql(self):
        company_code = self.request.query_params.get('company_code')
        m_status = self.request.query_params.get('m_status')
        nick_name = self.request.query_params.get('nick_name')
        if not company_code:
            raise CstException(RET.DATE_ERROR)
        self.query_sql += f" and a.company_code = {company_code}"
        if m_status:
            self.query_sql += f" and a.m_status = {m_status}"
        if nick_name:
            self.query_sql += f" and b.nick_name = {nick_name}"
        return self.query_sql

    def list(self, request, *args, **kwargs):
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        return CstResponse(RET.OK, data={'total': total, 'data': rows})

    @action(methods=["put"], detail=False)
    def examine(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.m_status = 2
        instance.save()
        return CstResponse(RET.OK)

    def perform_destroy(self, instance):
        instance.delete()


class EnterpriseDigitalClerkView(TyModelViewSet, NewSqlMixin):
    """
    企业数字员工视图 作者：xiaotao 版本号: 文档地址:
    """
    query_sql = enterprise_sqls.EnterpriseDigitalClerkSql
    sort_field = ["create_time"]
    main_table = "a"
    where = " and "
    queryset = CeEnterpriseDigitalClerk.objects.filter(is_delete=0)
    serializer_class = EnterpriseDigitalClerkSerializer
    lookup_field = "clerk_code"
    rabbit_mq = RabbitMqUtil()

    def set_query_sql(self):
        company_code = self.request.query_params.get('company_code')
        if not company_code:
            raise CstException(RET.DATE_ERROR)
        self.query_sql += f" and company_code = {company_code}"
        return self.query_sql

    def list(self, request, *args, **kwargs):
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        return CstResponse(RET.OK, data={'total': total, 'data': rows})

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        data = serializer.data
        headers = self.get_success_headers(data)
        mq_data = {
            'exchange': "digital_clerk_exchange",
            'queue': "digital_clerk_query",
            'routing_key': 'DigitalClerk',
            'type': "direct",
            "msg": {
                "clerk_code": data["clerk_code"],
                "company_code": data["company_code"],
                "knowledge_code": data["knowledge_code"],
            }
        }

        self.rabbit_mq.send_handle(mq_data)
        return CstResponse(RET.OK, data=data)

