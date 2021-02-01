# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import os
import sys
import time

import oss2
from oss2.crypto import AliKMSProvider

import config
"""
try:
    logging.basicConfig(filename=config.LogFile, encoding='utf-8', level=logging.DEBUG, format=config.LogFormat)  # only work on python>=3.9
except ValueError:
    logging.basicConfig(filename=config.LogFile, level=logging.DEBUG, format=config.LogFormat)
    logging.warning("Python版本小于3.9，logging将不会使用encoding参数")
"""


def Calculate_Local_File_sha256(file_name):
    """计算文件的sha256

    :param str file_name: 需要计算sha256的文件名
    """
    #start_time = time.time()
    m = hashlib.sha256()
    try:
        with open(file_name, 'rb') as fobj:
            if os.path.getsize(file_name) > config.MaxMemoryUsageAllow:
                while True:
                    data = fobj.read(config.MaxMemoryUsageAllow)
                    if not data:
                        break
                    m.update(data)
            else:
                m.update(fobj.read())
    except:
        logging.exception("Fail when opening the file: %s", file_name)
    #logging.debug("分块sha256 耗时 %f 秒" % (time.time() - start_time))
    return m.hexdigest()

class Oss_Operation(object):

    def __init__(self):
        self.__bucket = oss2.CryptoBucket(
            oss2.Auth(config.AccessKeyId, config.AccessKeySecret),
            config.OssEndpoint, config.bucket_name,
            crypto_provider=AliKMSProvider(config.AccessKeyId, config.AccessKeySecret, config.KMSRegion, config.CMKID)
        )
        self.__bucket_name = config.bucket_name

    def Uplode_File_Encrypted(self, local_file_name, remote_file_name):
        org_file_sha256 = Calculate_Local_File_sha256(local_file_name)  # TODO 从json获取文件sha256
        oss2.resumable_upload(
            self.__bucket, remote_file_name, local_file_name,
            # store=oss2.ResumableStore(root='/tmp'),
            multipart_threshold=1024*1024*50,
            part_size=1024*1024*50,
            num_threads=4,
            headers={
                "content-length": str(os.path.getsize(local_file_name)),
                "x-oss-server-side-encryption": "KMS",
                "x-oss-storage-class": "IA",
                "x-oss-meta-sha256": org_file_sha256
            }
        )

    def Download_Decrypted_File(self, local_file_name, remote_file_name):
        """从OSS下载并解密文件

        Args:
            local_file_name [str]
            remote_file_name [str]

        Returns:
            [type]: [description]
        """
        try:
            result = self.__bucket.get_object_to_file(remote_file_name, local_file_name)
        except:
            logging.exception("无法从oss下载文件" + remote_file_name)
        return result

    def Verify_Remote_File_Integrity(self, remote_file):
        result = self.__bucket.get_object(remote_file)
        sha256 = hashlib.sha256()
        for chunk in result:
            sha256.update(chunk)
        #print(result.headers)
        if sha256.hexdigest() == result.headers['x-oss-meta-sha256'].lower():
            print("校验通过")
            return True
        else:
            print("数据不匹配")
            return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    r_oss = Oss_Operation()
    r_oss.Uplode_File_Encrypted("sha256.json", "sha256.json")
