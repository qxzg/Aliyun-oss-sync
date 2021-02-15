# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import os
import time

import crcmod._crcfunext  # https://help.aliyun.com/document_detail/85288.html#h2-url-5
import oss2
from alibabacloud_kms20160120 import models as KmsModels
from alibabacloud_kms20160120.client import Client as KmsClient
from alibabacloud_tea_openapi import models as OpenApiModels

import config


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
        logger.exception("[Calculate_Local_File_sha256] Fail to open the file: %s", file_name)
        return False
    return m.hexdigest()


class Oss_Operation(object):

    def __init__(self, KMSAccessKeySecret=None):
        oss2.set_file_logger(config.LogFile, 'oss2', config.LogLevel)
        self.__bucket = oss2.CryptoBucket(
            oss2.Auth(config.OSSAccessKeyId, config.OSSAccessKeySecret),
            config.OssEndpoint, config.bucket_name,
            crypto_provider=oss2.crypto.AliKMSProvider(config.KMSAccessKeyId, KMSAccessKeySecret, config.KMSRegion, config.CMKID)
        )
        try:  # 检测Bucket是否存在
            self.__bucket.get_bucket_info()
        except oss2.exceptions.NoSuchBucket:
            logger.exception("Bucket:\"%s\"不存在" % config.bucket_name)
            raise ValueError("Bucket:\"%s\"不存在" % config.bucket_name)
        try:  # 检测KMS配置有效性
            KmsClient(OpenApiModels.Config(access_key_id=config.KMSAccessKeyId, access_key_secret=KMSAccessKeySecret, endpoint='kms.%s.aliyuncs.com' %
                                           config.KMSRegion)).generate_data_key(KmsModels.GenerateDataKeyRequest(key_id=config.CMKID))
        except:
            logger.exception("无法调用GenerateDataKey，请检查KMS相关配置")
            raise ValueError("无法调用GenerateDataKey，请检查KMS相关配置")
        del KMSAccessKeySecret
        self.__MAX_RETRIES = 3
        self.__bucket_name = config.bucket_name
        self.__remote_bace_dir = config.remote_bace_dir

    def Uplode_File_Encrypted(self, local_file_name, remote_file_name, storage_class='Standard', file_sha256=None):
        """使用KMS加密并上传文件

        Args:
            local_file_name (str): 本地文件路径
            remote_file_name (str): 远程文件路径
            storage_class (str, 可选): Object的存储类型，取值：Standard、IA、Archive和ColdArchive。默认值可在config中配置
            file_sha256 (str, 可选): 如不提供将会自动计算本地文件sha256
        """
        if not file_sha256:
            file_sha256 = Calculate_Local_File_sha256(local_file_name)
        retry_count = 0
        while True:
            try:
                retry_count += 1
                result = oss2.resumable_upload(
                    self.__bucket, remote_file_name, local_file_name,
                    store=oss2.ResumableStore(root=config.temp_dir),
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
                break
            except oss2.exceptions.ClientError:
                logger.exception("Uplode_File_Encrypted error, retrying time %d" % retry_count)
                time.sleep(retry_count)
                if retry_count >= self.__MAX_RETRIES:
                    logger.exception("[Uplode_File_Encrypted] Error")
                    raise oss2.exceptions.ClientError
        return result

    def Download_Decrypted_File(self, local_file_name, remote_file_name):
        """从OSS下载并解密文件

        Args:
            local_file_name (str)
            remote_file_name (str)
        """
        retry_count = 0
        while True:
            try:
                retry_count += 1
                result = self.__bucket.get_object_to_file(remote_file_name, local_file_name)
                break
            except oss2.exceptions.ClientError:
                logger.exception("Download_Decrypted_File error, retrying time %d" % retry_count)
                time.sleep(retry_count)
                if retry_count >= self.__MAX_RETRIES:
                    logger.exception("[Uplode_File_Encrypted] Error")
                    raise Exception
            except oss2.exceptions.NoSuchKey:
                logger.exception("无法从oss下载文件" + remote_file_name)
                raise oss2.exceptions.NoSuchKey
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
        retry_count = 0
        while True:
            try:
                retry_count += 1
                result = self.__bucket.get_object(remote_file)
                break
            except oss2.exceptions.ClientError:
                logger.exception("Verify_Remote_File_Integrity error, retrying time %d" % retry_count)
                time.sleep(retry_count)
                if retry_count >= self.__MAX_RETRIES:
                    logger.exception("[Verify_Remote_File_Integrity] Error")
                    raise oss2.exceptions.ClientError
        sha256 = hashlib.sha256()
        for chunk in result:
            sha256.update(chunk)
        if sha256.hexdigest() == result.headers['x-oss-meta-sha256'].lower():
            return True
        else:
            return False


def chaek_configs():
    # 检查目录参数合法性
    if config.local_bace_dir[0] != '/' or config.local_bace_dir[-1] != '/':
        logger.critical("本地工作目录(local_bace_dir)必须为带有前导和后导/的格式")
        raise ValueError("本地工作目录(local_bace_dir)必须为带有前导和后导/的格式")
    if config.temp_dir[0] != '/' or config.temp_dir[-1] != '/':
        logger.critical("临时目录(temp_dir)必须为带有前导和后导/的格式")
        raise ValueError("临时目录(temp_dir)必须为带有前导和后导/的格式")
    if config.remote_bace_dir[0] == '/' or config.remote_bace_dir[-1] != '/':
        logger.critical("远端工作目录(remote_bace_dir)必须为带有后导/的格式")
        raise ValueError("远端工作目录(remote_bace_dir)必须为带有后导/的格式")
    for path in config.backup_dirs:
        if path[0] == '/' or path[-1] != '/':
            logger.critical("本地备份目录(backup_dirs)必须为带有后导/的格式")
            raise ValueError("本地备份目录(backup_dirs)必须为带有后导/的格式")
    if type(config.backup_exclude) != tuple:
        logger.critical("备份排除目录(backup_exclude_dirs)必须为tuple类型")
        raise ValueError("备份排除目录(backup_exclude_dirs)必须为tuple类型")
    for path in config.backup_exclude:
        if path[0] == '/':
            logger.critical("备份排除目录(backup_exclude_dirs)必须为不带前导/的相对路径")
            raise ValueError("备份排除目录(backup_exclude_dirs)必须为不带前导/的相对路径")
    # 检查目录是否存在
    try:
        os.chdir(config.local_bace_dir)
    except FileNotFoundError:
        logger.exception("本地工作目录'%s'无效，请检查设置" % config.local_bace_dir)
        raise ValueError("本地工作目录'%s'无效，请检查设置" % config.local_bace_dir)
    try:
        for dirs in config.backup_dirs:
            assert os.path.isdir(dirs)
    except FileNotFoundError:
        logger.exception("备份目录'%s'无效，请检查设置" % dirs)
        raise ValueError("备份目录'%s'无效，请检查设置" % dirs)
    if not os.path.exists(config.temp_dir):
        logger.info("临时文件夹%s不存在，将会自动创建")
        os.makedirs(config.temp_dir)
    # 检查oss参数合法性
    if not config.default_storage_class in ['Standard', 'IA', 'Archive', 'ColdArchive']:
        logger.critical("default_storage_class取值错误，必须为Standard、IA、Archive或ColdArchive")
        raise ValueError("default_storage_class取值错误，必须为Standard、IA、Archive或ColdArchive")
    if not config.OssEndpoint.startswith("https://"):
        logger.critical("OSS Endpoint必须以https://开头")
        raise ValueError("OSS Endpoint必须以https://开头")
    return True


if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(config.LogLevel)
    formatter = logging.Formatter(config.LogFormat)
    chlr = logging.StreamHandler()
    chlr.setFormatter(formatter)
    try:
        fhlr = logging.FileHandler(filename=config.LogFile, encoding='utf-8')  # only work on python>=3.9
    except ValueError:
        fhlr = logging.FileHandler(filename=config.LogFile)
    fhlr.setFormatter(formatter)
    logger.addHandler(chlr)
    logger.addHandler(fhlr)
    logger.info('this is info')
    logger.debug('this is debug')
    r_oss = Oss_Operation(str(input("请输入AK为\"%s\"的KMS服务的SK：" % config.KMSAccessKeyId)))
    # r_oss.Download_Decrypted_File("run-backup.sh", "nas-backup/main-pool/shell/run-backup.sh")
