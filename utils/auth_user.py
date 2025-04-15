#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from rest_framework import authentication
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from language.language_pack import RET
from server_chat import settings
from utils import constants
from utils.cst_class import CstException
from utils.request_utils import get_response


class AuthUser(object):

    def __init__(self, user_id, user_code, source, role, user_name="", is_real_name=1, invitation_code=""):
        self.user_id = user_id
        self.user_code = user_code
        self.user_name = user_name
        self.role = role  # user, guess,
        self.source = source
        self.is_real_name = is_real_name        # 是否实名
        self.invitation_code = invitation_code        # 邀请码


# class CustomBackend(ModelBackend):
#     def authenticate(self, request, username=None, password=None, **kwargs):
#         authorization = request.META.get('HTTP_AUTHORIZATION')
#         source = request.META.get('HTTP_SOURCE') or ""
#         tag = request.META.get('HTTP_ROLE') or constants.ROLE_GUESS
#
#         if not authorization:
#             raise CstException(RET.AUTH_ERR)
#         user_dict = self.get_user_info(authorization, tag)  # 获取用户信息
#         if not user_dict:
#             raise CstException(RET.USER_ERR)
#
#         user = AuthUser(user_dict['user_code'], user_dict['user_code'], source=source, role=tag)
#         return user
#
#     @staticmethod
#     def get_user_info(authorization, tag):
#         head = {"AUTHORIZATION": authorization, "ROLE": tag}
#         url = settings.SERVER_USER_URL + "api/user/get_user_data"
#         return get_response(url, head=head)

auth_path = ["/api/chat/async_chat_session", "/api/chat/new_chat_session"]


class UserAuthentication(authentication.BaseAuthentication):
    """
    登录验证
    """

    def authenticate(self, request):
        authorization = request.META.get('HTTP_AUTHORIZATION')
        source = request.META.get('HTTP_SOURCE') or ""
        tag = request.META.get('HTTP_ROLE') or constants.ROLE_USER
        path = request.path
        if path in auth_path:
            http_status = 400
        else:
            http_status = 200

        if not authorization:
            raise CstException(RET.AUTH_ERR, status=http_status)
        user_dict = self.get_user_info(authorization, tag, http_status)  # 获取用户信息
        if not user_dict:
            raise CstException(RET.USER_ERR, status=http_status)

        user = AuthUser(user_dict['user_code'], user_dict['user_code'], source=source, role=tag,
                        is_real_name=user_dict["is_real_name"], invitation_code=user_dict["invitation_code"])
        return user, None

    @staticmethod
    def get_user_info(authorization, tag, status):
        head = {"AUTHORIZATION": authorization, "ROLE": tag}
        url = settings.SERVER_USER_URL + "api/user/get_user_data"
        return get_response(url, head=head, status=status)
