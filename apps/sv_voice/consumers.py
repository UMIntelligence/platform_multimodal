#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import io
import json
import logging
import queue
import time
import uuid

import asyncio
from threading import Timer
from urllib.parse import parse_qs

import websockets

from channels.generic.websocket import AsyncWebsocketConsumer, WebsocketConsumer
from django_redis import get_redis_connection

import nls
from apps.sv_voice.utils import send_start_params, send_audio
from sc_chat.utils import charges_api
from server_chat import settings
from utils import constants
from utils.sso_utils import ToOss
from utils.str_utils import base64_to_binary

logger = logging.getLogger(__name__)


class AliWebSocketConsumer(WebsocketConsumer):

    def test_on_sentence_begin(self, message, *args):
        """
        当实时语音识别开始时的回调参数
        :param message:
        :param args:
        :return:
        """
        self.send(message)

    def test_on_sentence_end(self, message, *args):
        """
        当实时语音识别结束时的回调参数
        :param message: 
        :param args: 
        :return: 
        """""
        self.send(message)

    def test_on_start(self, message, *args):
        """
        当实时语音识别就绪时的回调参数
        :param message:
        :param args:
        :return:
        """
        self.send(message)

    def test_on_error(self, message, *args):
        """
        当实时语音识别错误时的回调参数
        :param message:
        :param args:
        :return:
        """
        self.send(message)

    def test_on_close(self, *args):
        """
        关闭
        :param args:
        :return:
        """
        print("---close")
        self.close()

    def test_on_result_chg(self, message, *args):
        """
        实时语音识别返回中间结果时的回调参数
        :param message:
        :param args:
        :return:
        """
        self.send(message)

    def test_on_completed(self, message, *args):
        """
        实时语音识别返回最终识别结果时的回调参数
        :param message:
        :param args:
        :return:
        """
        self.send(message)

    def connect(self):
        uri = settings.A_URI + "/ws/v1"
        redis_conn = get_redis_connection('default')
        token = redis_conn.get("ali_audio")
        token = token.decode("utf-8")
        self.sr = nls.NlsSpeechTranscriber(
            url=uri,
            token=token,
            appkey=settings.A_APP_KEY,
            on_sentence_begin=self.test_on_sentence_begin,
            on_sentence_end=self.test_on_sentence_end,
            on_start=self.test_on_start,
            on_result_changed=self.test_on_result_chg,
            on_completed=self.test_on_completed,
            on_error=self.test_on_error,
            on_close=self.test_on_close,
        )
        self.accept()
        # 启动心跳检测任务

    def disconnect(self, close_code):
        print("close-----")

    def receive(self, text_data=None, bytes_data=None):
        # print(type(text_data))
        # print(text_data, "---", bytes_data)
        if text_data:
            try:
                message = json.loads(text_data)
                s_type = message.get("type")
                if s_type == "FINISH":  # 结束帧
                    time.sleep(2)
                    self.sr.stop()
                elif s_type == "START":
                    format_str = message.get("format") or constants.FORMAT_STR
                    r = self.sr.start(aformat=format_str, enable_punctuation_prediction=True,
                                      enable_intermediate_result=True,
                                      enable_inverse_text_normalization=True)
                else:
                    base64_data = message.get("base64_data")
                    binary_data = base64_to_binary(base64_data)
                    slices = zip(*(iter(binary_data),) * 640)
                    for i in slices:
                        self.sr.send_audio(bytes(i))

            except Exception as e:
                print("eeee")
                self.send(text_data=json.dumps({"err_no": 334, "err_msg": "数据异常"}))

        # 将接收到的数据发送给第三方WebSocket服务
        if bytes_data:
            print("---------", bytes_data)
            slices = zip(*(iter(bytes_data),) * 640)
            for i in slices:
                self.sr.send_audio(i)    # 发送数据


class BaiduWebSocketConsumer(AsyncWebsocketConsumer):
    # HEARTBEAT_INTERVAL = 5  # 心跳间隔时间（秒）

    async def connect(self):
        uri = settings.B_URI + "?sn=" + str(uuid.uuid1())
        self.websocket = await websockets.connect(uri)
        await self.accept()
        # 创建一个任务来接收并处理第三方返回的数据
        asyncio.create_task(self.receive_data())
        # 启动心跳检测任务

    async def disconnect(self, close_code):
        print("close-----")
        await self.websocket.close()

    async def receive_data(self):
        while True:
            try:
                data = await self.websocket.recv()

                # 处理接收到的数据，可以将其发送给其他频道组或者直接发送给WebSocket客户端
                await self.send(text_data=data)
                print(data)
            except websockets.exceptions.ConnectionClosed:
                await self.close()
                break

    async def receive(self, text_data=None, bytes_data=None):
        print(type(text_data))
        print(text_data, "---", bytes_data)
        if text_data:
            try:
                message = json.loads(text_data)
                s_type = message.get("type")
                if s_type == "START":  # 开始帧
                    dev_pid = message.get("dev_pid") or constants.DEV_PID
                    format_str = message.get("format") or constants.FORMAT_STR
                    await send_start_params(self.websocket, dev_pid, format_str)
                elif s_type == "SEND":
                    base64_data = message.get("base64_data")
                    binary_data = base64_to_binary(base64_data)
                    await send_audio(self.websocket, binary_data)
                else:
                    await self.websocket.send(text_data)
            except Exception as e:
                print("eeee")
                await self.send(text_data=json.dumps({"err_no": 334, "err_msg": "数据异常"}))

        # 将接收到的数据发送给第三方WebSocket服务
        # if bytes_data:
        #     # print(bytes_data)
        #     await send_audio(self.websocket, bytes_data)    # 发送数据


# class AsyncAliTTSConsumer(AsyncWebsocketConsumer):
#     URL = "wss://nls-gateway-cn-shenzhen.aliyuncs.com/ws/v1"
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # 初始化断开连接任务为None
#         self.disconnect_task = None
#
#     def start_disconnect_timer(self):
#         # 创建断开连接的任务，10秒后执行
#         self.disconnect_task = asyncio.create_task(self.disconnect_in(10))
#
#     async def disconnect_in(self, delay):
#         # 等待指定的秒数，然后调用close方法断开连接
#         await asyncio.sleep(delay)
#         await self.close()
#
#     async def close(self, code=None):
#         print("Closing connection")
#         # 调用父类的close方法来真正的断开连接
#         await super().close()
#
#     async def connect(self):
#         """
#         连接
#         :return:
#         """
#         await self.accept()
#         query_string = self.scope["query_string"].decode()
#         parameters = parse_qs(query_string)
#         try:
#             token = parameters.get("token")[0]
#         except TypeError as e:
#             await self.send(text_data=json.dumps({"code": 40017, "msg": "请上传token"}))
#             # 然后关闭连接
#             await self.close()
#         else:
#             self.tts = nls.NlsSpeechSynthesizer(url=self.URL, token=token, appkey=settings.A_APP_KEY,
#                                                 long_tts=True,
#                                                 on_metainfo=self.on_metainfo,
#                                                 on_data=self.on_data,
#                                                 on_completed=self.on_completed,
#                                                 on_error=self.on_error,
#                                                 on_close=self.on_close)
#
#             self.start_disconnect_timer()   # 连接后开始断开连接的定时器
#
#     async def disconnect(self, close_code):
#         print("close-----")
#         if self.disconnect_task:
#             self.disconnect_task.cancel()
#         self.disconnect_task = None
#
#     async def receive(self, text_data=None, bytes_data=None):
#         if self.disconnect_task:
#             self.disconnect_task.cancel()
#         self.start_disconnect_timer()
#
#         try:
#             req_data = json.loads(text_data)
#             text = req_data.get("text")
#             voice = req_data.get("voice")
#             speech_rate = req_data.get("speech_rate") or 0
#             pitch_rate = req_data.get("pitch_rate") or 0
#             if not all([text, voice]):
#                 raise
#         except Exception as e:
#             await self.send(text_data=json.dumps(json.dumps({"code": 40017, "msg": "参数错误"})))
#         else:
#
#             await self.__test_run(text, voice, speech_rate, pitch_rate)
#
#     async def on_metainfo(self, message, *args):
#         print("on_metainfo message=>{}".format(message))
#
#     async def on_error(self, message, *args):
#         print("on_error args=>{}".format(args))
#
#     async def on_close(self, *args):
#         print("on_close: args=>{}".format(args))
#         try:
#             self.tts.shutdown()
#         except Exception as e:
#             print("close file failed since:", e)
#
#     async def on_data(self, data, *args):
#         print(data)
#         await self.send(bytes_data=data)
#
#     async def on_completed(self, message, *args):
#         print("on_completed:args=>{} message=>{}".format(args, message))
#
#     async def __test_run(self, text, voice, speech_rate, pitch_rate, enable_ptts=True, volume=50):
#         ex = {"enable_ptts": enable_ptts}
#         r = self.tts.start(text, voice=voice, aformat="wav", volume=volume, speech_rate=speech_rate,
#                                  pitch_rate=pitch_rate, completed_timeout=500, ex=ex)


class AliTTSConsumer(WebsocketConsumer):
    URL = "wss://nls-gateway-cn-shenzhen.aliyuncs.com/ws/v1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.disconnect_timer = None
        self.__f = io.BytesIO()
        self.pending_tasks = queue.Queue()
        self.enable_ptts = False
        self.long_tts = False

    def close(self, code=None):
        print("Closing connection")
        # 调用父类的close方法来真正的断开连接
        if self.disconnect_timer is not None:
            self.disconnect_timer.cancel()

        self.__f.close()
        super().close()

    def start_disconnect_timer(self):
        # 创建断开连接的任务，15秒后执行
        if self.disconnect_timer is not None:
            self.disconnect_timer.cancel()
        self.disconnect_timer = Timer(15, self.close)
        self.disconnect_timer.start()

    def connect(self):
        """
        连接
        :return:
        """

        self.accept()
        query_string = self.scope["query_string"].decode()
        parameters = parse_qs(query_string)
        try:
            self.token = parameters.get("token")[0]
            enable_ptts = parameters.get("enable_ptts")
            long_tts = parameters.get("long_tts")
            if enable_ptts:
                self.enable_ptts = True
            if long_tts:
                self.long_tts = True
        except TypeError as e:
            self.send(text_data=json.dumps({"code": 40017, "msg": "请上传token"}))
            # 然后关闭连接
            self.close()
        else:
            self.start_disconnect_timer()

    def disconnect(self, close_code):
        print("close-----")
        with self.pending_tasks.mutex:
            self.pending_tasks.queue.clear()

    def receive(self, text_data=None, bytes_data=None):
        self.start_disconnect_timer()

        try:
            req_data = json.loads(text_data)
            task_info = {
                'text': req_data.get('text', ''),
                'voice': req_data.get('voice', ''),
                'speech_rate': req_data.get('speech_rate', 0),
                'pitch_rate': req_data.get('pitch_rate', 0)
            }
            action_type = req_data.get("action_type") or "send"
            if action_type == "send" and not all([task_info['text'], task_info['voice']]):
                raise
        except Exception as e:
            self.send(text_data=json.dumps(json.dumps({"code": 40017, "msg": "参数错误"})))
        else:
            print(req_data)
            if action_type == "send":
                # self.__test_run(task_info['text'], task_info['voice'], task_info['speech_rate'], task_info['pitch_rate'])
                self.pending_tasks.put(task_info)
                if self.pending_tasks.qsize() == 1:
                    self.process_next_task()
            else:
                oss_obj = ToOss()
                oss_url = oss_obj.main("ali_tts", file_con=self.__f.getvalue(), file_extension="wav")
                self.send(text_data=json.dumps({"code": 20000, "msg": "", "data": oss_url}))
                self.close()

    def on_metainfo(self, message, *args):
        print("on_metainfo message=>{}".format(message))

    def on_error(self, message, *args):
        print("on_error args=>{}".format(args))

    def on_close(self, *args):
        print("on_close: args=>{}".format(args))
        # try:
        #     self.tts.shutdown()
        # except Exception as e:
        #     print("close file failed since:", e)

    def on_data(self, data, *args):
        # print("----------111")
        self.send(bytes_data=data)
        self.__f.write(data)

    def on_completed(self, message, *args):
        print("on_completed:args=>{} message=>{}".format(args, message))

    def __test_run(self, text, voice, speech_rate, pitch_rate, volume=50):
        ex = {"enable_ptts": self.enable_ptts}
        tts = nls.NlsSpeechSynthesizer(url=self.URL, token=self.token, appkey=settings.A_APP_KEY,
                                       long_tts=self.long_tts,
                                       on_metainfo=self.on_metainfo,
                                       on_data=self.on_data,
                                       on_completed=self.on_completed,
                                       on_error=self.on_error,
                                       on_close=self.on_close)
        # wait_complete=True 只有上一个任务处理完才进行下一个,解决音频顺序错乱问题
        tts.start(text, voice=voice, aformat="wav", volume=volume, speech_rate=speech_rate,
                  pitch_rate=pitch_rate, wait_complete=True, completed_timeout=500, ex=ex)

    def process_next_task(self):
        # 弹出任务并处理
        print("---------", self.pending_tasks.qsize())
        if self.pending_tasks.qsize() > 0:
            task_info = self.pending_tasks.get()
            self.__test_run(task_info['text'], task_info['voice'], task_info['speech_rate'], task_info['pitch_rate'])
            self.pending_tasks.task_done()


class SdDemo(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 初始化断开连接任务为None
        self.disconnect_task = None
        self.user_code = None
        self.charge_task = None

    def start_charge_timer(self):
        # 创建扣费的任务，每60秒扣费一次
        self.charge_task = asyncio.create_task(self.charge_in(60))

    async def charge_in(self, delay):
        while True:
            # 等待指定的秒数，然后调用charges_api进行扣费
            await asyncio.sleep(delay)
            await charges_api(self.user_code, 1800)

    def start_disconnect_timer(self):
        # 创建断开连接的任务，10秒后执行
        self.disconnect_task = asyncio.create_task(self.disconnect_in(1800))

    async def disconnect_in(self, delay):
        # 等待指定的秒数，然后调用close方法断开连接
        await asyncio.sleep(delay)
        await self.close()

    async def close(self, code=None):
        print("Closing connection")
        # 调用父类的close方法来真正的断开连接
        await super().close()

    async def disconnect(self, close_code):
        print("close-----")
        if self.disconnect_task:
            self.disconnect_task.cancel()
        self.disconnect_task = None
        if self.charge_task:
            self.charge_task.cancel()
        self.charge_task = None

    async def connect(self):
        """
        连接
        :return:
        """
        await self.accept()
        query_string = self.scope["query_string"].decode()
        parameters = parse_qs(query_string)
        try:
            token = parameters.get("token")[0]
            self.user_code = parameters.get("user_code")[0]
        except TypeError as e:
            await self.send(text_data=json.dumps({"code": 40017, "msg": "请上传token"}))
            # 然后关闭连接
            await self.close()
        self.start_disconnect_timer()   # 连接后开始断开连接的定时器
        self.start_charge_timer()    # 连接后开始扣费的定时器

    async def receive(self, text_data=None, bytes_data=None):
        if self.disconnect_task:
            self.disconnect_task.cancel()
        self.start_disconnect_timer()

