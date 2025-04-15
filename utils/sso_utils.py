#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import logging
import uuid
import oss2
import requests

from language.language_pack import RET
from server_chat import settings
from utils.cst_class import CstException

logger = logging.getLogger(__name__)


class ToOss(object):
    """
    阿里云OSS图片上传类
    """

    def __init__(self):
        self.bucket = oss2.Bucket(oss2.Auth(settings.ACCESS_KEY_ID, settings.ACCESS_KEY_SECRET),
                                  settings.END_POINT, settings.BUCKET_NAME)

    def upload_to_oss(self, image_name, oss_dir, cate, image_url="", file_con=''):
        """
        上传图片到OSS

        :param image_url: 网络图片的URL
        :param image_name: 图片的名称
        :param cate: 分类
        :param oss_dir: oss目录
        :param file_con:
        :return: 上传成功返回0，否则返回-1
        """
        object_name = oss_dir + '/' + cate + '/' + image_name

        if file_con:
            try:
                result = self.bucket.put_object(object_name, file_con)
                # print(result)
            except Exception as e:
                print(e)
                return -1
        else:
            # 如果是网络图片，先下载，然后上传
            for i in range(3):
                try:
                    response = requests.get(image_url, timeout=20)
                    if response.status_code != 200:
                        continue
                        # raise CstException(RET.NOT_FOUND, "图片获取失败，请重试")
                    result = self.bucket.put_object(object_name, response.content)
                    break
                except Exception as e:
                    if i == 2:
                        logger.error(f"""oss错误：{e}""")
                        return -1
                    continue

        return 0

    def main(self, cate, oss_dir="chat", img_url="", file_con='', file_extension="png"):
        """
        主函数，创建Bucket对象，并调用uploadToOss函数上传图片

        :param img_url: 图片的URL
        :param cate: 分类
        :param oss_dir: 下级目录
        :param file_con:
        :param file_extension:
        :return: 上传成功返回新的URL，否则返回空字符串
        """
        img_name = str(uuid.uuid4()) + f'.{file_extension}'
        i_ret = self.upload_to_oss(img_name, oss_dir, cate, image_url=img_url, file_con=file_con)

        if i_ret != 0:
            return ''

        else:
            new_url = oss_dir + "/" + cate + '/' + img_name
            # print(new_url)
            return new_url

    def delete_object(self, oss_url):
        self.bucket.delete_object(oss_url)

    def batch_delete_objects(self, oss_urls):
        result = self.bucket.batch_delete_objects(oss_urls)
        return result

    def batch_get_objects(self, oss_urls):
        return self.bucket.get_object(oss_urls)


init = ToOss()
url = ''
cate = 'test'
item_id = 1

# init = ToOss()
# new_url = init.main(cate, oss_dir=oss_dir, file_con=image.read())
# print(a)
