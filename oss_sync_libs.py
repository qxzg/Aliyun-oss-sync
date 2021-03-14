# -*- coding: utf-8 -*-
import hashlib
import itertools
import json
import logging
import os
from time import sleep 
from getpass import getpass

import crcmod._crcfunext  # https://help.aliyun.com/document_detail/85288.html#h2-url-5
import oss2
import requests
from alibabacloud_kms20160120 import models as KmsModels
from alibabacloud_kms20160120.client import Client as KmsClient
from alibabacloud_tea_openapi import models as OpenApiModels
from numpy import square
from rich.progress import Progress, ProgressColumn, Text
from tenacity import (retry, retry_if_exception_type, stop_after_attempt,
                      wait_exponential)

import config

logger = logging.getLogger("oss_sync_libs")


class Colored(object):
    BLACK = '\033[0;30m'       # 红色
    RED = '\033[0;31m'       # 红色
    GREEN = '\033[0;32m'     # 绿色
    YELLOW = '\033[0;33m'    # 黄色
    BLUE = '\033[0;34m'      # 蓝色
    FUCHSIA = '\033[0;35m'   # 紫红色
    CYAN = '\033[0;36m'      # 青蓝色
    WHITE = '\033[0;37m'     # 白色

    #: no color
    END = '\033[0m'      # 终端默认颜色

    def color_str(self, color, s):
        return '%s%s%s' % (getattr(self, color), str(s), self.END)

    def black(self, s: str):
        return self.color_str('BLACK', s)

    def red(self, s: str):
        return self.color_str('RED', s)

    def green(self, s: str):
        return self.color_str('GREEN', s)

    def yellow(self, s: str):
        return self.color_str('YELLOW', s)

    def blue(self, s: str):
        return self.color_str('BLUE', s)

    def fuchsia(self, s: str):
        return self.color_str('FUCHSIA', s)

    def cyan(self, s: str):
        return self.color_str('CYAN', s)

    def white(self, s: str):
        return self.color_str('WHITE', s)


def SCT_Push(title: str, message: str) -> bool:
    url = "https://sctapi.ftqq.com/%s.send" % (config.SCT_Send_Key)
    sc_req = requests.post(url=url, data={'title': title, 'desp': message})
    if sc_req.json()['data']['error'] == "SUCCESS":
        logger.info("SCT Push Success!")
        return True
    else:
        logger.exception("SCT Push ERROR! "+sc_req.json())
        return False


class FileCount(ProgressColumn):
    """呈现剩余文件数量和总数, e.g. '已处理 666 / 共 23333 个文件'."""

    def render(self, task: "Task"):
        return Text(f" 已处理 {int(task.completed)} / 共 {int(task.total)} 个文件 ", style="progress.download")


def Calculate_Local_File_sha256(file_name: str):
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
        color = Colored()
        if not KMSAccessKeySecret:
            KMSAccessKeySecret = str(getpass("请输入AK为\"%s\"的KMS服务的SK：" % color.red(config.KMSAccessKeyId)))
        self.__OssEndpoint = 'https://' + config.OssEndpoint
        self.__bucket = oss2.CryptoBucket(
            oss2.Auth(config.OSSAccessKeyId, config.OSSAccessKeySecret),
            self.__OssEndpoint, config.bucket_name,
            crypto_provider=oss2.crypto.AliKMSProvider(config.KMSAccessKeyId, KMSAccessKeySecret, config.KMSRegion, config.CMKID)
        )
        try:  # 检测Bucket是否存在
            self.__bucket.get_bucket_info()
        except oss2.exceptions.NoSuchBucket:
            logger.critical("Bucket:\"%s\"不存在" % config.bucket_name)
            raise ValueError("Bucket:\"%s\"不存在" % config.bucket_name)
        try:  # 检测KMS配置有效性
            KmsClient(OpenApiModels.Config(access_key_id=config.KMSAccessKeyId, access_key_secret=KMSAccessKeySecret, endpoint='kms.%s.aliyuncs.com' %
                                           config.KMSRegion)).generate_data_key(KmsModels.GenerateDataKeyRequest(key_id=config.CMKID))
        except:
            logger.critical("无法调用GenerateDataKey，请检查KMS相关配置")
            raise ValueError("无法调用GenerateDataKey，请检查KMS相关配置")
        del KMSAccessKeySecret
        self.__MAX_RETRIES = 3
        self.__bucket_name = config.bucket_name
        self.__remote_bace_dir = config.remote_bace_dir
        if os.name == 'nt':
            self.__ping_cmd = "ping -n 1 " + config.OssEndpoint
        elif os.name == 'posix':
            self.__ping_cmd = "ping -c 1 " + config.OssEndpoint
        else:
            raise OSError("无法识别操作系统")
        if os.system(self.__ping_cmd) != 0:
            logger.error("无法连接至%s，请检查OssEndpoint和网络配置" % (config.OssEndpoint))
            raise ValueError("无法连接至%s，请检查OssEndpoint和网络配置" % (config.OssEndpoint))

    def Uplode_File_Encrypted(self, local_file_name, remote_object_name, storage_class='Standard', file_sha256=None, cache_control='no-store', check_sha256_before_uplode=False):
        """使用KMS加密并上传文件

        Args:
            local_file_name (str): 本地文件路径
            remote_object_name (str): 远程文件路径
            storage_class (str, 可选): Object的存储类型，取值：Standard、IA、Archive和ColdArchive。默认值为Standard
            file_sha256 (str, 可选): 如不提供将会自动计算本地文件sha256
            cache_control (str, 可选)
            check_sha256_before_uplode (bool, 可选): 是否在上传之前对比远端文件的sha256，如相同则跳过上传
        """
        if not file_sha256:
            file_sha256 = Calculate_Local_File_sha256(local_file_name)
        retry_count = 0
        if check_sha256_before_uplode:
            try:
                remote_object_sha256 = self.Get_Remote_File_Meta(remote_object_name)['x-oss-meta-sha256']
            except:
                remote_object_sha256 = file_sha256
            if remote_object_sha256 == file_sha256:
                logger.info("[Uplode_File_Encrypted]sha256相同，跳过%s文件的上传" % (local_file_name))
                return 200
        while True:
            try:

                retry_count += 1
                result = oss2.resumable_upload(
                    self.__bucket, remote_object_name, local_file_name,
                    store=oss2.ResumableStore(root=config.temp_dir),
                    multipart_threshold=1024*1024*50,
                    part_size=1024*1024*50,
                    num_threads=4,
                    headers={
                        "content-length": str(os.path.getsize(local_file_name)),
                        "Cache-Control": cache_control,
                        "x-oss-server-side-encryption": "KMS",
                        "x-oss-storage-class": storage_class,
                        "x-oss-meta-sha256": file_sha256
                    }
                )
                break
            except (oss2.exceptions.ClientError, oss2.exceptions.RequestError, ConnectionResetError) as err:
                if retry_count < self.__MAX_RETRIES:
                    logger.error("[Uplode_File_Encrypted] error, retrying time %d" % retry_count)
                    logger.error(err)
                else:
                    logger.exception("[Uplode_File_Encrypted] Error")
                    raise oss2.exceptions.RequestError
                sleep(square(retry_count) * 10)
                while os.system(self.__ping_cmd) != 0:
                    logger.error("无法连接网络，10秒后重试")
                    sleep(10)
        return 200

    def Download_Decrypted_File(self, local_file_name, remote_object_name, versionId=None):
        """从OSS下载并解密文件

        Args:
            local_file_name (str)
            remote_object_name (str)
            versionId (str, 可选)
        """
        retry_count = 0
        while True:
            try:
                retry_count += 1
                if versionId:
                    result = self.__bucket.get_object_to_file(remote_object_name, local_file_name, params={'versionId': versionId})
                else:
                    result = self.__bucket.get_object_to_file(remote_object_name, local_file_name)
                break
            except (oss2.exceptions.ClientError, oss2.exceptions.RequestError, ConnectionResetError) as err:
                if retry_count < self.__MAX_RETRIES:
                    logger.error("[Download_File_Encrypted] error, retrying time %d" % retry_count)
                    logger.error(err)
                else:
                    logger.exception("[Download_File_Encrypted] Error")
                    raise oss2.exceptions.RequestError
                sleep(square(retry_count) * 10)
                while os.system(self.__ping_cmd) != 0:
                    logger.error("无法连接网络，10秒后重试")
                    sleep(10)
            except oss2.exceptions.NoSuchKey:
                logger.exception("无法从oss下载文件" + remote_object_name)
                return 404
        return result

    @retry(retry=retry_if_exception_type(oss2.exceptions.RequestError), reraise=True, wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(7))
    def Delete_Remote_files(self, delete_list: list):
        """删除OSS中的文件

        Args:
            delete_list (list): 需要删除的文件列表，绝对对路径

        Returns:
            list: [description]
        """
        for i in range(0, (len(delete_list) // 1000) + 1):
            self.__bucket.batch_delete_objects(delete_list[i * 1000:(i * 1000) + 999])
        return

    @retry(retry=retry_if_exception_type(oss2.exceptions.RequestError), reraise=True, wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(7))
    def Copy_remote_files(self, copy_list: dict, storage_class='Standard'):
        """复制远程文件

        Args:
            copy_list (dits): Key:目标文件, velue:源文件
        """
        for dst_obj, src_obj in copy_list.items():
            self.__bucket.copy_object(self.__bucket_name, src_obj, dst_obj, headers={'x-oss-storage-class': storage_class})

    def Verify_Remote_File_Integrity(self, remote_object):
        retry_count = 0
        while True:
            try:
                retry_count += 1
                result = self.__bucket.get_object(remote_object)
                break
            except oss2.exceptions.ClientError:
                logger.exception("Verify_Remote_File_Integrity error, retrying time %d" % retry_count)
                sleep(retry_count)
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

    def Get_Remote_File_Meta(self, remote_object: str, versionId=None):
        """获取一个远程文件的元信息

        Args:
            remote_object (str)
            versionId (str, optional)

        Returns:
            list: https://help.aliyun.com/document_detail/31984.html?#title-xew-l4g-a20
        """
        try:
            if versionId:
                objectmeta = self.__bucket.head_object(remote_object, params={'versionId': versionId})
            else:
                objectmeta = self.__bucket.head_object(remote_object)
        except oss2.exceptions.NotFound:
            logger.warning("请求的object %s 不存在" % (remote_object))
            return 404
        except oss2.exceptions.ServerError as e:
            logger.error(e)
        else:
            return objectmeta.headers

    def Restore_Remote_File(self, remote_object, versionId=""):
        """解冻一个Object
        api文档: https://help.aliyun.com/document_detail/52930.html

        Args:
            remote_object (str)
            versionId (str, optional)

        Returns:
            int: http响应码
        """
        try:
            self.__bucket.restore_object(remote_object)
        except oss2.exceptions.OperationNotSupported:
            logger.warning("您正在试图解冻一个非归档或冷归档类型的Object: %s" % (remote_object))
            return 400
        except oss2.exceptions.RestoreAlreadyInProgress:
            logger.info("目标object %s 正在解冻中" % (remote_object))
            return 409
        except oss2.exceptions.NoSuchKey:
            logger.warning("您正在解冻一个不存在的object %s" % (remote_object))
            return 404
        else:
            return 200


def Chaek_Configs():
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
    if config.OssEndpoint.startswith("http"):
        logger.critical("OSS Endpoint请直接填写域名")
        raise ValueError("OSS Endpoint请直接填写域名")
    return True


if __name__ == "__main__":
    logger.setLevel(config.LogLevel)
    formatter = logging.Formatter(config.LogFormat)
    chlr = logging.StreamHandler()
    chlr.setFormatter(formatter)
    logger.addHandler(chlr)
    r_oss = Oss_Operation('')
