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
    """计算sha256

    Args:
        file_name (str): 需要计算sha256的文件名

    Returns:
        str: 文件的sha256
    """
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
        logging.exception("[Calculate_Local_File_sha256] Fail to open the file: %s", file_name)
        return False
    return m.hexdigest()

class Oss_Operation(object):

    def __init__(self):
        if not config.OssEndpoint.startswith("https://"):
            logging.critical("OSS Endpoint必须以https://开头")
            raise Exception("OSS Endpoint必须以https://开头")
        self.__bucket = oss2.CryptoBucket(
            oss2.Auth(config.AccessKeyId, config.AccessKeySecret),
            config.OssEndpoint, config.bucket_name,
            crypto_provider=AliKMSProvider(config.AccessKeyId, config.AccessKeySecret, config.KMSRegion, config.CMKID)
        )
        self.__bucket_name = config.bucket_name
        self.__remote_bace_dir = config.remote_bace_dir

    def Uplode_File_Encrypted(self, local_file_name, remote_file_name, storage_class = config.default_storage_class, file_sha256 = '-1'):
        """使用KMS加密并上传文件

        Args:
            local_file_name (str): 本地文件路径
            remote_file_name (str): 远程文件路径
            storage_class (str, 可选): Object的存储类型，取值：Standard、IA、Archive和ColdArchive。默认值可在config中配置
            file_sha256 (str, 可选): 如不提供将会自动计算本地文件sha256
        """
        if file_sha256 == '-1':
            file_sha256 = Calculate_Local_File_sha256(local_file_name)
        result = oss2.resumable_upload(
            self.__bucket, remote_file_name, local_file_name,
            # store=oss2.ResumableStore(root='/tmp'),
            multipart_threshold=1024*1024*50,
            part_size=1024*1024*50,
            num_threads=4,
            headers={
                "content-length": str(os.path.getsize(local_file_name)),
                "x-oss-server-side-encryption": "KMS",
                "x-oss-storage-class": storage_class,
                "x-oss-meta-sha256": file_sha256
            }
        )
        return result

    def Download_Decrypted_File(self, local_file_name, remote_file_name):
        """从OSS下载并解密文件

        Args:
            local_file_name (str)
            remote_file_name (str)
        """
        try:
            result = self.__bucket.get_object_to_file(remote_file_name, local_file_name)
        except:
            logging.exception("无法从oss下载文件" + remote_file_name)
        return result

    def Delete_Remote_files(self, delete_list):
        """删除OSS中的文件

        Args:
            delete_list (list): 需要删除的文件列表，绝对对路径

        Returns:
            list: [description]
        """
        for i in range(0, (len(delete_list) // 1000) + 1):
            self.__bucket.batch_delete_objects(delete_list[i * 1000:(i * 1000) + 999])
        return

    def Copy_remote_files(self, copy_list):
        """复制远程文件

        Args:
            copy_list (dits): Key:目标文件, velue:源文件
        """
        for dst_obj, src_obj in copy_list.items():
            self.__bucket.copy_object(self.__bucket_name, src_obj, dst_obj)

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
