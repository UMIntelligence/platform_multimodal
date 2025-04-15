#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import binascii
import datetime
import hashlib
import hmac
import json
import requests
import urllib

from language.language_pack import RET
from server_chat import settings
from utils.cst_class import CstException


class VolcengineSigner(object):

    @staticmethod
    def get_canonical_query_string(param_dict):
        target = sorted(param_dict.items(), key=lambda x: x[0], reverse=False)
        canonical_query_string = urllib.parse.urlencode(target)
        return canonical_query_string

    @staticmethod
    def get_hmac_encode16(data):
        return binascii.b2a_hex(hashlib.sha256(data.encode("utf-8")).digest()).decode(
            "ascii"
        )

    @staticmethod
    def get_volc_signature(secret_key, data):
        return hmac.new(secret_key, data.encode("utf-8"), digestmod=hashlib.sha256).digest()

    def get_hashmac_headers(
            self,
            domain,
            region,
            service,
            canonical_query_string,
            http_request_method,
            canonical_uri,
            contenttype,
            payload_sign,
            ak,
            sk,
    ):
        utc_time_sencond = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        utc_time_day = datetime.datetime.utcnow().strftime("%Y%m%d")
        credential_scope = utc_time_day + "/" + region + "/" + service + "/request"
        headers = {
            "content-type": contenttype,
            "x-date": utc_time_sencond,
        }
        canonical_headers = (
                "content-type:"
                + contenttype
                + "\n"
                + "host:"
                + domain
                + "\n"
                + "x-content-sha256:"
                + "\n"
                + "x-date:{}".format(utc_time_sencond)
                + "\n"
        )
        signed_headers = "content-type;host;x-content-sha256;x-date"
        canonical_request = (
                http_request_method
                + "\n"
                + canonical_uri
                + "\n"
                + canonical_query_string
                + "\n"
                + canonical_headers
                + "\n"
                + signed_headers
                + "\n"
                + payload_sign
        )
        string_to_sign = (
                "HMAC-SHA256"
                + "\n"
                + utc_time_sencond
                + "\n"
                + credential_scope
                + "\n"
                + self.get_hmac_encode16(canonical_request)
        )
        signing_key = self.get_volc_signature(
            self.get_volc_signature(
                self.get_volc_signature(
                    self.get_volc_signature(sk.encode("utf-8"), utc_time_day), region
                ),
                service,
            ),
            "request",
        )
        signature = binascii.b2a_hex(self.get_volc_signature(signing_key, string_to_sign)).decode(
            "ascii"
        )
        headers[
            "Authorization"
        ] = "HMAC-SHA256 Credential={}/{}, SignedHeaders={}, Signature={}".format(
            ak, credential_scope, signed_headers, signature
        )
        return headers


class TrainStatus(VolcengineSigner):
    domain = "open.volcengineapi.com"
    region = "cn-north-1"
    service = "speech_saas_prod"

    def action_tts_train_status(
            self,
            speaker_ids,
            app_id: int = settings.VG_TTS_APP_ID,
            ak: str = settings.VG_AK,
            sk: str = settings.VG_SK,
    ) -> requests.Response:
        params_body = {
            "AppID": app_id,
            "SpeakerIDs": speaker_ids,  # 如果希望获取全量speaker id，可以不传入该参数
        }
        canonical_query_string = "Action=ActivateMegaTTSTrainStatus&Version=2023-11-07"
        url = "https://" + self.domain + "/?" + canonical_query_string
        content_type = "application/json; charset=utf-8"
        payload_sign = self.get_hmac_encode16(json.dumps(params_body))
        headers = self.get_hashmac_headers(
            self.domain,
            self.region,
            self.service,
            canonical_query_string,
            "POST",
            "/",
            content_type,
            payload_sign,
            ak,
            sk,
        )
        try:
            submit_resp = requests.post(url=url, headers=headers, data=json.dumps(params_body)).json()
            print(submit_resp)
        except Exception as e:
            raise CstException(RET.MAX_C_ERR)
        result = submit_resp.get("Result")
        if not result:
            raise CstException(RET.DATE_ERROR, "启用失败")
        if result.get("Statuses")[0].get("State") != "Active":
            raise CstException(RET.DATE_ERROR, "启用失败")

        return submit_resp
