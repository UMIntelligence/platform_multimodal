#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import json
import operator
from functools import reduce

from django.db import connections
from django.db.models import Q

from language.language_pack import RET
from utils.cst_class import CstException, CstResponse


def dict_fetchall(cursor):
    """""Return all rows from a cursor as a dict"""
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]


class PublicSearch:
    def filter_queryset(self, data, queryset):
        q_data = json.loads(data)
        joinType = q_data.get("type")
        querys = q_data.get("query")

        up_dict = {
            "=": "",
            ">": "__gt",
            "<": "__lt",
            ">=": "__gte",
            "<=": "__lte",
            "c": "__contains",
            "in": "__in",
            "b": "__range",
            "s": "__startswith",
            "e": "__endswith",
            "isNull": "__isnull"
        }
        down_dict = {
            "!=": "",
            "nc": "__contains",
            "nin": "__in",
            "nb": "__range",
            "ns": "__startswith",
            "ne": "__endswith",
            "isNotNull": "__isnull"
        }
        filters = []
        for query in querys:

            try:
                value = query[2]
            except:
                value = ''

            if query[1] == "c" or query[1] == "nc":
                if value[0] == "%" and value[-1] == "%":
                    value = value[1:-1]
                elif value[0] == "%":
                    value = value[1:]
                    query[1] = "e" if query[1] == "c" else "ne"
                elif value[-1] == "%":
                    value = value[:-1]
                    query[1] = "s" if query[1] == "c" else "ns"
            elif query[1] == "in" or query[1] == "nin":
                value = [int(i) for i in value.split(",")]
            elif query[1] == "b" or query[1] == "nb":
                value = [i for i in value]
                if len(value) != 2:
                    return queryset

            elif query[1] == "isNull":
                value = True
            elif query[1] == "isNotNull":
                value = False

            else:
                pass

            if query[1] in up_dict.keys():
                s_key = query[0] + up_dict[query[1]]

                if query[1] == 'isNull':
                    filters.append(Q((s_key, value)) | Q((query[0], '')))
                elif (value == '' and query[1] == '='):
                    filters.append(Q((s_key, value)) | Q((query[0] + '__isnull', True)))
                else:
                    filters.append(Q((s_key, value)))
            else:
                s_key = query[0] + down_dict[query[1]]

                if query[1] == 'isNotNull':
                    filters.append(Q((s_key, value)) | ~Q((query[0], '')))
                else:
                    filters.append(~Q((s_key, value)))

        if len(filters) == 0:
            return queryset
        else:
            operatorTag = operator.and_ if joinType == 1 else operator.or_
            queryset = queryset.filter(reduce(operatorTag, filters))

            return queryset


class TyMixin(object):
    datelap = ''

    keywords = []
    sortField = []
    sort_type = "asc"

    querylist = [
        # 'get_querysetDataPower',  # 行权限
        # 'dateLapSwitch',  # 日期过滤转换
        # 'deptFilter',  # 部门过滤
        'search'  # 高级搜索和快速查询
    ]

    departField = ''  # 行权限字段名
    teamField = ''

    def get_queryset(self):

        queryset = super().get_queryset()

        for queryfun in self.querylist:
            queryset = getattr(self, queryfun)(queryset)

        sortlist = self.get_soortField()

        return queryset.order_by(*sortlist)

    # 调用快速搜索和高级搜索
    def search(self, queryset):

        # 关键字搜索
        keywords = self.request.query_params.get('keyword', '')

        queryset = self.advanceSearch(queryset)
        if keywords != '':
            queryset = self.quickSearch(queryset, keywords)

        return queryset

    # 快速搜索
    def get_keywordField(self):

        quick = self.request.query_params.get('quicksearch', None)
        # if quick is None:
        #     tmptarget = FieldSheetModel.objects.select_related('menuid').filter(menuid__id=self.menuid, isquicksearch=1)
        #     target = [x.name for x in tmptarget]
        # else:
        target = [quick]
        if len(target) > 0:
            return target
        else:
            return self.keywords

    def quickSearch(self, querySet, keyword):
        sList = []

        keywordFields = self.get_keywordField()

        self.serializer_class.formKeywords = keywordFields
        self.serializer_class.keyword = keyword

        for field in keywordFields:
            sList.append(Q((field, keyword)))

        if sList:
            return querySet.filter(reduce(operator.or_, sList))
        else:
            return querySet

    # 高级搜索
    def advanceSearch(self, queryset):

        query = self.request.query_params.get('query', '{"type":1,"query":[]}')
        if query.find('"query":[]') < 0:
            s = PublicSearch()
            queryset = s.filter_queryset(query, queryset)

        return queryset

    # 部门过滤
    # def deptFilter(self, queryset):
    #
    #     org_id = self.request.query_params.get('org_id', None)
    #     if not org_id:
    #         org_id = self.request.query_params.get('orgid', None)
    #
    #     return queryset

    # 时间参数映射
    def dateLapSwitch(self, queryset):
        try:
            datelap = self.request.query_params['dateLap']

            if len(datelap) == 4:
                queryset = queryset.filter(**{self.datelap + '__startswith': datelap})
            elif len(datelap) > 0:
                queryset = queryset.filter(**{self.datelap: datelap[:7]})
        except:

            try:
                datelap = self.request.query_params.getlist('dateLap[]')
                if len(datelap) > 0:
                    dateLen = len(datelap[0])
                    queryset = queryset.filter(
                        **{f'{self.datelap[:dateLen]}__range': (datelap[0][:dateLen], datelap[1][:dateLen])})
            except:
                pass

        return queryset

    # 行数据权限
    # def get_querysetDataPower(self, queryset):
    #     if self.departField:
    #         username = self.request.user.username
    #         try:
    #             dataPower, depts = get_role_menu_permission(username)
    #             try:
    #                 depts = depts.split(",")
    #                 depts_l = [int(dept[1:]) for dept in depts if dept != '' and dept != '0' and dept != 's1']
    #             except:
    #                 depts_l = None
    #
    #             staff = UserModel.objects.get(username=self.request.user.username)
    #             if int(dataPower) == 2:  # //本部门及下属部门
    #                 if depts_l:
    #                     depts_l.append(staff.department)
    #                     for department in sub_department_tree(staff.department):  # 添加该用户下面所有的下属部门
    #                         depts_l.append(department)
    #
    #                     queryset = queryset.filter(**{f"{self.departField}__in": depts_l})
    #                 else:
    #                     queryset = queryset.filter(**{self.departField: staff.department})
    #
    #             elif int(dataPower) == 3:  # //本部门
    #                 if depts_l:
    #                     depts_l.append(staff.department)
    #                     queryset = queryset.filter(**{f"{self.departField}__in": depts_l})
    #                 else:
    #                     queryset = queryset.filter(**{self.departField: staff.department})
    #
    #             elif int(dataPower) == 4:  # 个人
    #                 pass
    #         except:
    #             return queryset
    #     else:
    #         pass
    #     return queryset

    def get_soortField(self):

        order = self.request.query_params.get('sorttype', self.sort_type).split(',')
        sortName = self.request.query_params.get('sortname', self.sortField[0]).split(',')

        sortlist = []
        for i in range(len(sortName)):
            try:
                tmpSort = order[i]
                sortlist.append("%s%s" % ("-" if tmpSort == 'desc' else '', sortName[i]))
            except:
                sortlist.append(sortName[i])
        return sortlist if len(sortlist) > 0 else self.sortField


class TySqlMixin(object):

    main_table = ''

    keywords = []
    sort_field = []
    sort_type = 'desc'

    filter_fields = []

    filters = []
    filter_holder = []

    query_sql = ''
    query_sql_holder = ''

    db = 'default'
    where = ' Where '

    query_list = [
        # 'filter',  # url或默认过滤条件
        # 'search',  # 高级搜索和快速查询
        'add_filter',  # sql添加过滤条件
    ]

    def get_query_sql(self):
        return self.query_sql

    def get_query_total(self):

        self.filter_holder = []
        for n_filter in self.filters:
            self.filter_holder.append(n_filter)

        self.query_sql_holder = self.get_query_sql()

        for query_fun in self.query_list:
            getattr(self, query_fun)()

        # 分页
        total = self.pagination()

        return total

    def add_filter(self):
        filter_str = []

        tmp_filters = tuple(self.filter_holder)
        for item in tmp_filters:

            if item[0] == '__group__':

                op = " " + item[1] + " "
                tmp_filter = "(" + op.join(item[2]) + ")"

            elif item[1] == 'in':

                tmp_filter = "%s in (%s)" % (item[0], ','.join(["'" + str(x) + "'" for x in item[2]]))
            else:
                if item[1] == 'between':
                    tmp_filter = "%s %s %s" % (item[0], item[1], item[2])
                elif item[1] == '*':
                    tmp_filter = item[2]
                else:
                    tmp_filter = "%s %s '%s'" % (item[0], item[1], item[2])

            if tmp_filter != '':
                filter_str.append(tmp_filter)

        if len(filter_str) > 0:
            self.query_sql_holder = self.query_sql_holder + self.where + ' and '.join(filter_str)

    # url参数过滤
    # def filter(self):
    #
    #     if len(self.filter_fields) > 0:
    #         for field in self.filter_fields:
    #             value = self.request.query_params.get(field, None)
    #             if value:
    #                 self.filter_holder.append([self.convert_field(field), '=', str(value)])

    # 调用快速搜索和高级搜索
    # def search(self):
    #     query = self.request.query_params.get('query', '{"type":1,"query":[]}')
    #     if query.find('"query":[]') < 0:
    #         self.advance_search(query)
    #     else:
    #         keywords = self.request.query_params.get('keyword', '')
    #         if keywords != '':
    #             self.quick_search(keywords)

    # 高级搜索
    def advance_search(self, query):

        advance_list = []
        a_query = json.loads(query)
        query_list = a_query['query']

        for item in query_list:
            query_str = self.search_key_convert(item)

            if query_str != '':
                advance_list.append(query_str)

        if len(advance_list) > 0:
            op = 'and' if int(a_query['type']) == 1 else 'or'
            self.filter_holder.append(['__group__', op, advance_list])

    def convert_field(self, field):

        if field.find('__') >= 0:
            return field.replace('__', '.')
        elif self.main_table:
            return self.main_table + '.' + field
        else:
            return field

    def search_key_convert(self, query):
        """ 高级查询中的标记转成sql方式"""

        op_list = ["=", ">", "<", ">=", "<="]
        op_dict = {
            "!=": "{0}<>'{1}'",
            "c": "{0} LIKE '%{1}%'",
            "b": "{0} BETWEEN '{1}' AND '{2}'",
            "s": "{0} NOT LIKE '%{1}%'",
            "e": "{0} NOT LIKE '%{1}%'",
            "nc": "{0} NOT LIKE '%{1}%'",
            "nin": "{0} NOT IN ('{1}')",
            "nb": "{0} NOT BETWEEN '{1}' AND '{2}'",
            "ns": "{0} NOT LIKE '%{1}%'",
            "ne": "{0} NOT LIKE '%{1}%'",
        }

        op = query[1]
        field = self.convert_field(query[0])
        val = ''
        if op in op_list:
            val = "{0}{1}'{2}'".format(field, op, query[2])

        else:
            if op == 'b' or op == 'nb':
                # bt = query[2].split("-")
                bt = query[2]
                if len(bt) == 2:
                    val = op_dict.get(op).format(field, bt[0], bt[1])
            else:
                val = op_dict.get(op).format(field, query[2])

        return val

    def quick_search(self, keyword):
        s_list = []

        keyword_fields = self.get_keyword_field()
        keyword = self.request.query_params.get('keyword', keyword)

        if keyword:
            for field in keyword_fields:
                tmp = "%s = '%s'" % (self.convert_field(field), keyword)
                s_list.append(tmp)

            if len(s_list) > 0:
                self.filter_holder.append(['__group__', 'or', s_list])

    # 快速搜索
    def get_keyword_field(self):

        return self.keywords

    def count_func(self, count_sql):
        # 总数
        with connections[self.db].cursor() as cursor:
            sum_sql = "Select count(*) From ( %s ) as a" % count_sql

            cursor.execute(sum_sql)
            total = cursor.fetchone()
        return total[0] if total else 0

    # 分页
    def pagination(self):

        page_size = self.request.query_params.get('page_size', None)
        page = self.request.query_params.get('page', 1)

        if page_size:  # 需要分页

            total = self.count_func(self.query_sql_holder)

            start = (int(page) - 1) * int(page_size)

            limit = "limit %s,%s" % (start, page_size)

            self.add_orders()
            self.query_sql_holder = self.query_sql_holder + ' ' + limit

            return total
        else:
            self.add_orders()
            return -1

    def add_orders(self):

        orders = self.query_order()
        if orders != '':
            self.query_sql_holder = self.query_sql_holder + ' Order By ' + orders

    def query_order(self):

        order = self.request.query_params.get('sort_type', self.sort_type).split(',')
        sort_name = self.request.query_params.get('sort_name', '')

        if sort_name == '':
            sort_name = self.sort_field
        else:
            sort_name = sort_name.split(',')

        sort_list = []
        for i in range(len(sort_name)):
            try:
                tmp_sort = order[i]
            except:
                tmp_sort = 'asc'

            sort_list.append("%s %s" % (self.convert_field(sort_name[i]), tmp_sort))

        return ','.join(sort_list)

    def list(self, request, *args, **kwarg):
        """
        列表视图
        :param request:
        :param args:
        :param kwarg:
        :return:
        """
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        return CstResponse(RET.OK, data={'total': total, 'data': rows})


class NewSqlMixin(TySqlMixin):

    def get_query_total(self):

        # self.filter_holder = []
        # for n_filter in self.filters:
        #     self.filter_holder.append(n_filter)

        self.query_sql_holder = self.get_query_sql

        # for query_fun in self.query_list:
        #     getattr(self, query_fun)()

        # 分页
        total = self.pagination()

        return total

    @property
    def get_query_sql(self):
        return self.set_query_sql()

    def set_query_sql(self):
        raise Exception("请重写")
