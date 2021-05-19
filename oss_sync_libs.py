# -*- coding: utf-8 -*-
import argparse
import hashlib
import logging
import os
import subprocess
from getpass import getpass
from time import sleep

import oss2
import requests
from alibabacloud_kms20160120 import models as KmsModels
from alibabacloud_kms20160120.client import Client as KmsClient
from alibabacloud_tea_openapi import models as OpenApiModels
from numpy import square
from rich.progress import ProgressColumn, Text
from tenacity import (retry, retry_if_exception_type, stop_after_attempt,
                      wait_exponential)

import config

logger = logging.getLogger("oss_sync_libs")


class Colored(object):
    __color_code = {
        'BLACK': '\033[0;30m',  # 黑色
        'RED': '\033[0;31m',  # 红色
        'GREEN': '\033[0;32m',  # 绿色
        'YELLOW': '\033[0;33m',  # 黄色
        'BLUE': '\033[0;34m',  # 蓝色
        'FUCHSIA': '\033[0;35m',  # 紫红色
        'CYAN': '\033[0;36m',  # 青蓝色
        'WHITE': '\033[0;37m',  # 白色
        #: no color
        'END': '\033[0m'  # 终端默认颜色
        }

    def color_str(self, __color, s):
        return '%s%s%s' % (self.__color_code[__color], str(s), self.__color_code['END'])

    def black(self, s):
        return self.color_str('BLACK', s)

    def red(self, s):
        return self.color_str('RED', s)

    def green(self, s):
        return self.color_str('GREEN', s)

    def yellow(self, s):
        return self.color_str('YELLOW', s)

    def blue(self, s):
        return self.color_str('BLUE', s)

    def fuchsia(self, s):
        return self.color_str('FUCHSIA', s)

    def cyan(self, s):
        return self.color_str('CYAN', s)

    def white(self, s):
        return self.color_str('WHITE', s)


color = Colored()
try:
    import crcmod._crcfunext
except ModuleNotFoundError:
    input("%s crcmod的C扩展模式安装失败，会造成上传文件效率低下，请参考 https://help.aliyun.com/document_detail/85288.html#h2-url-5 安装devel。\n按ENTER键继续..." % (color.red('[Warning]')))


def sct_push(title: str, message: str) -> bool:
    """Server酱·Turbo版推送"""
    url = "https://sctapi.ftqq.com/%s.send" % config.SCT_Send_Key
    sc_req = requests.post(url=url, data={'title': title, 'desp': message})
    if sc_req.json()['data']['error'] == "SUCCESS":
        logger.info("SCT Push Success!")
        return True
    else:
        logger.exception("SCT Push ERROR! " + sc_req.json())
        return False


class FileCount(ProgressColumn):
    """呈现剩余文件数量和总数, e.g. '已处理 666 / 共 23333 个文件'."""

    def render(self, task):
        return Text(f"已处理 {int(task.completed)} / 共 {int(task.total)} 个文件", style="progress.download")


def calculate_local_file_sha256(file_name: str):
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
        logger.exception("[calculate_local_file_sha256] Fail to open the file: %s", file_name)
        return False
    return m.hexdigest()


class OssOperation(object):  # TODO 使用@retry重写重试部分

    def __init__(self, kms_access_key_secret=None):
        oss2.set_file_logger(config.LogFile, 'oss2', config.LogLevel)
        if not kms_access_key_secret:
            kms_access_key_secret = str(getpass("请输入AK为\"%s\"的KMS服务的SK：" % color.red(config.KMSAccessKeyId)))
        self.__OssEndpoint = 'https://' + config.OssEndpoint
        self.__bucket = oss2.CryptoBucket(
            oss2.Auth(config.OSSAccessKeyId, config.OSSAccessKeySecret),
            self.__OssEndpoint, config.bucket_name,
            crypto_provider=oss2.crypto.AliKMSProvider(config.KMSAccessKeyId, kms_access_key_secret, config.KMSRegion, config.CMKID)
            )

        try:  # 检测Bucket是否存在
            self.__bucket.get_bucket_info()
        except oss2.exceptions.NoSuchBucket:
            logger.critical("Bucket:\"%s\"不存在" % config.bucket_name)
            raise ValueError("Bucket:\"%s\"不存在" % config.bucket_name)

        try:  # 检测KMS配置有效性
            KmsClient(OpenApiModels.Config(access_key_id=config.KMSAccessKeyId, access_key_secret=kms_access_key_secret,
                                           endpoint='kms.%s.aliyuncs.com' % config.KMSRegion)).generate_data_key(KmsModels.GenerateDataKeyRequest(key_id=config.CMKID))
        except:
            logger.critical("无法调用KMS服务生成密钥，请检查相关配置，以及SK是否输入正确")
            raise ValueError("无法调用KMS服务生成密钥，请检查相关配置，以及SK是否输入正确")
        del kms_access_key_secret

        self.__ping_cmd = ["ping", "1", config.OssEndpoint]
        if os.name == 'nt':
            self.__ping_cmd.insert(1, "-n")
        elif os.name == 'posix':
            self.__ping_cmd.insert(1, "-c")
        else:
            raise OSError("无法识别操作系统")
        if subprocess.run(self.__ping_cmd, capture_output=True).returncode != 0:
            logger.error("无法连接至%s，请检查OssEndpoint和网络配置" % config.OssEndpoint)
            raise ValueError("无法连接至%s，请检查OssEndpoint和网络配置" % config.OssEndpoint)

        self.__restore_configuration_model = [oss2.models.RESTORE_TIER_EXPEDITED, oss2.models.RESTORE_TIER_STANDARD, oss2.models.RESTORE_TIER_BULK]

    def encrypt_and_upload_files(self, local_file_name, remote_object_name, storage_class='Standard', file_sha256=None, cache_control='no-store',
                                 compare_sha256_before_uploading=False):
        """使用KMS加密并上传文件

        Args:
            local_file_name (str): 本地文件路径
            remote_object_name (str): 远程文件路径
            storage_class (str, 可选): Object的存储类型，取值：Standard、IA、Archive和ColdArchive。默认值为Standard
            file_sha256 (str, 可选): 如不提供将会自动计算本地文件sha256
            cache_control (str, 可选)
            compare_sha256_before_uploading (bool, 可选): 是否在上传之前对比远端文件的sha256，如相同则跳过上传
        """
        if not file_sha256:
            file_sha256 = calculate_local_file_sha256(local_file_name)
        retry_count = 0
        if compare_sha256_before_uploading:
            try:
                remote_object_sha256 = self.get_remote_file_headers(remote_object_name)['x-oss-meta-sha256']
            except:
                remote_object_sha256 = file_sha256
            if remote_object_sha256 == file_sha256:
                logger.info("[encrypt_and_upload_files]sha256相同，跳过%s文件的上传" % local_file_name)
                return 200
        while True:
            try:

                retry_count += 1
                oss2.resumable_upload(
                    self.__bucket, remote_object_name, local_file_name,
                    store=oss2.ResumableStore(root=config.temp_dir),
                    multipart_threshold=1024 * 1024 * 50,
                    part_size=1024 * 1024 * 50,
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
                if retry_count < config.Max_Retries:
                    logger.error("[encrypt_and_upload_files] error, retrying time %d" % retry_count)
                    logger.error(err)
                else:
                    logger.exception("[encrypt_and_upload_files] Error")
                    raise oss2.exceptions.RequestError
                sleep(square(retry_count) * 10)
                while subprocess.run(self.__ping_cmd, capture_output=True).returncode != 0:
                    logger.error("无法连接网络，10秒后重试")
                    sleep(10)
        return 200

    def download_and_decrypt_file(self, local_file_name: str, remote_object_name: str, version_id: str = None, verify_integrity: bool = False):
        """从OSS下载并解密文件

        Args:
            local_file_name (str)
            remote_object_name (str)
            version_id (str, 可选)
            verify_integrity: 设置为True会在下载之后校验sha256
        """
        retry_count = 0
        if not version_id:
            req_params = None
        else:
            req_params = {'versionId': version_id}

        while True:
            try:
                retry_count += 1
                req = self.__bucket.get_object_to_file(remote_object_name, local_file_name, params=req_params)
                break
            except (oss2.exceptions.ClientError, oss2.exceptions.RequestError, ConnectionResetError) as err:
                if retry_count < config.Max_Retries:
                    logger.error("[Download_File_Encrypted] error, retrying time %d" % retry_count)
                    logger.error(err)
                else:
                    logger.exception("[Download_File_Encrypted] Error")
                    raise oss2.exceptions.RequestError
                sleep(square(retry_count) * 10)
                while subprocess.run(self.__ping_cmd, capture_output=True).returncode != 0:
                    logger.error("无法连接网络，10秒后重试")
                    sleep(10)
            except oss2.exceptions.NoSuchKey:
                logger.error("无法找到文件" + remote_object_name)
                return 404
        if verify_integrity:
            if calculate_local_file_sha256(local_file_name) == req.headers['x-oss-meta-sha256']:
                return 200
            else:
                logger.error('[download_and_decrypt_file] Object: %s 校验不通过' % remote_object_name)
                raise
        return 200

    @retry(retry=retry_if_exception_type(oss2.exceptions.RequestError), reraise=True, wait=wait_exponential(multiplier=1, min=2, max=60),
           stop=stop_after_attempt(config.Max_Retries))
    def delete_remote_files(self, delete_list: list):
        """删除OSS中的文件

        Args:
            delete_list (list): 需要删除的文件列表，绝对对路径
        """
        for i in range(0, (len(delete_list) // 1000) + 1):
            self.__bucket.batch_delete_objects(delete_list[i * 1000:(i * 1000) + 999])

    @retry(retry=retry_if_exception_type(oss2.exceptions.RequestError), reraise=True, wait=wait_exponential(multiplier=1, min=2, max=60),
           stop=stop_after_attempt(config.Max_Retries))
    def copy_remote_files(self, copy_list: dict, storage_class=oss2.BUCKET_STORAGE_CLASS_STANDARD):
        """复制远程文件

        Args:
            copy_list (dits): {目标文件: 源文件}
            storage_class (str)
        """
        for dst_obj, src_obj in copy_list.items():
            self.__bucket.copy_object(config.bucket_name, src_obj, dst_obj, headers={'x-oss-storage-class': storage_class})

    @retry(retry=retry_if_exception_type(oss2.exceptions.RequestError) | retry_if_exception_type(oss2.exceptions.ClientError), reraise=True,
           wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(config.Max_Retries))
    def verify_remote_file_integrity(self, remote_object) -> bool:
        """校验远端文件哈希值，将文件下载、解密至内存中计算sha256并与oss header中的sha256比对

        Args:
            remote_object (str): 待校验的文件
        """
        result = self.__bucket.get_object(remote_object)
        sha256 = hashlib.sha256()
        for chunk in result:
            sha256.update(chunk)
        if sha256.hexdigest() == result.headers['x-oss-meta-sha256'].lower():
            return True
        else:
            return False

    @retry(retry=retry_if_exception_type(oss2.exceptions.RequestError) | retry_if_exception_type(oss2.exceptions.ClientError), reraise=True,
           wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(config.Max_Retries))
    def get_remote_file_headers(self, remote_object: str, version_id: str = None):
        """获取一个远程文件的元信息

        Args:
            remote_object (str)
            version_id (str, optional)

        Returns:
            dict: https://help.aliyun.com/document_detail/31984.html?#title-xew-l4g-a20
        """
        if not version_id:
            req_params = None
        else:
            req_params = {'versionId': version_id}

        try:
            __object_header = self.__bucket.head_object(remote_object, params=req_params)
        except oss2.exceptions.NotFound:
            logger.warning("请求的object %s 不存在" % remote_object)
            return 404
        else:
            return __object_header.headers

    @retry(retry=retry_if_exception_type(oss2.exceptions.RequestError) | retry_if_exception_type(oss2.exceptions.ClientError), reraise=True,
           wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(config.Max_Retries))
    def get_remote_file_size(self, remote_object: str, version_id: str = None) -> int:
        """获取一个远程Object的Content-Length

        Args:
            remote_object (str)
            version_id (str, optional)

        Returns:
            int: 文件大小
        """
        if not version_id:
            req_params = None
        else:
            req_params = {'versionId': version_id}

        try:
            __object_header = self.__bucket.get_object_meta(remote_object, params=req_params)
        except oss2.exceptions.NoSuchKey:
            logger.warning("[get_remote_file_size] 请求的Object: %s 不存在" % remote_object)
            return 404
        else:
            return int(__object_header.headers['Content-Length'])

    @retry(retry=retry_if_exception_type(oss2.exceptions.RequestError) | retry_if_exception_type(oss2.exceptions.ClientError), reraise=True,
           wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(config.Max_Retries))
    def restore_remote_file(self, remote_object: str, version_id: str = None, restore_configuration: int = None) -> int:
        """解冻一个Object
        api文档: https://help.aliyun.com/document_detail/52930.html

        Args:
            remote_object (str)
            version_id (str, optional)
            restore_configuration (int) 解冻优先级, 取值范围:
                0: 1个小时之内解冻完成
                1: 5小时之内解冻完成
                2: 10小时之内解冻完成

        Returns:
            int: http响应码
        """
        if restore_configuration:
            restore_configuration = self.__restore_configuration_model[restore_configuration]
        if not version_id:
            req_params = None
        else:
            req_params = {'versionId': version_id}

        try:
            self.__bucket.restore_object(remote_object, input=restore_configuration, params=req_params)
        except oss2.exceptions.OperationNotSupported:
            logger.warning("[restore_remote_file] 您正在试图解冻一个非归档或冷归档类型的Object: %s" % remote_object)
            return 400
        except oss2.exceptions.RestoreAlreadyInProgress:
            logger.info("[restore_remote_file] 目标Object: \"%s\" 正在解冻中" % remote_object)
            return 409
        except oss2.exceptions.NoSuchKey:
            logger.warning("[restore_remote_file] 您正在解冻一个不存在的Object %s" % remote_object)
            return 404
        else:
            return 200

    def check_restore_status(self, remote_object: str, version_id: str = None) -> int:
        """检查Object的解冻状态

        Args:
            remote_object (str)
            version_id (str)

        Returns: int
            200: 已完成解冻
            409: 正在解冻中
            410: 没有提交解冻或者解冻已超时

        """
        __headers = self.get_remote_file_headers(remote_object, version_id=version_id)
        if 'x-oss-restore' in __headers:
            if __headers['x-oss-restore'] == 'ongoing-request="true"':
                return 409
            else:
                return 200
        elif type(__headers) == int:
            if __headers == 404:
                return 404
        else:
            return 410


def bytes_to_str(size) -> str:
    """存储单位人性化转换，精确为最大单位值+小数点后三位"""

    def __str_of_size(__integer, __remainder, __level):
        if __integer >= 1024:
            __remainder = __integer % 1024
            __integer //= 1024
            __level += 1
            return __str_of_size(__integer, __remainder, __level)
        else:
            return __integer, __remainder, __level

    size = int(size)
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    integer, remainder, level = __str_of_size(size, 0, 0)
    if level + 1 > len(units):
        level = -1
    return '%.3f %s' % (integer + remainder * 0.001, units[level])


def check_configs():
    # 检查目录参数合法性
    if config.remote_base_dir[0] == '/' or config.remote_base_dir[-1] != '/':
        logger.critical("远端工作目录(remote_base_dir)必须为带有后导/的格式")
        raise ValueError("远端工作目录(remote_base_dir)必须为带有后导/的格式")
    if type(config.backup_exclude) != tuple:
        logger.critical("备份排除目录(backup_exclude_dirs)必须为tuple类型")
        raise ValueError("备份排除目录(backup_exclude_dirs)必须为tuple类型")

    if not os.path.isabs(config.local_base_dir) or config.local_base_dir[-1] != '/':
        logger.critical("本地工作目录(local_base_dir)必须为带有后导/的绝对路径")
        raise ValueError("本地工作目录(local_base_dir)必须为带有后导/的绝对路径")
    if not os.path.isabs(config.temp_dir) or config.temp_dir[-1] != '/':
        logger.critical("临时目录(temp_dir)必须为带有后导/的绝对路径")
        raise ValueError("临时目录(temp_dir)必须为带有后导/的绝对路径")

    for path in config.backup_exclude:
        if path[0] == '/':
            logger.critical("备份排除目录(backup_exclude_dirs)不可带有前导/")
            raise ValueError("备份排除目录(backup_exclude_dirs)不可带有前导/")
    for path in config.backup_dirs:
        if (path[0] == '/' or path[-1] != '/') and os.path.isabs(path):
            logger.critical("本地备份目录(backup_dirs)必须为带有后导/的相对路径")
            raise ValueError("本地备份目录(backup_dirs)必须为带有后导/的相对路径")
    if config.remote_base_dir.startswith("sha256"):
        logger.critical("remote_base_dir不应以sha256开头，可能与哈希存储冲突")
        raise ValueError("remote_base_dir不应以sha256开头，可能与哈希存储冲突")

    # 检查目录是否存在
    if not os.path.isdir(config.local_base_dir):
        logger.exception("本地工作目录'%s'无效，请检查设置" % config.local_base_dir)
        raise ValueError("本地工作目录'%s'无效，请检查设置" % config.local_base_dir)
    for dirs in config.backup_dirs:
        dirs = config.local_base_dir + dirs
        if not os.path.isdir(dirs):
            logger.exception("备份目录'%s'无效，请检查设置" % dirs)
            raise ValueError("备份目录'%s'无效，请检查设置" % dirs)
    if not os.path.exists(config.temp_dir):
        logger.info("临时文件夹%s不存在，将会自动创建")
        os.makedirs(config.temp_dir)
    # 检查oss参数合法性
    if config.default_storage_class not in [oss2.BUCKET_STORAGE_CLASS_STANDARD, oss2.BUCKET_STORAGE_CLASS_IA, oss2.BUCKET_STORAGE_CLASS_ARCHIVE,
                                            oss2.BUCKET_STORAGE_CLASS_COLD_ARCHIVE]:
        logger.critical("default_storage_class取值错误，必须为Standard、IA、Archive或ColdArchive")
        raise ValueError("default_storage_class取值错误，必须为Standard、IA、Archive或ColdArchive")
    if config.OssEndpoint.startswith("http"):
        logger.critical("OSS Endpoint请直接填写域名")
        raise ValueError("OSS Endpoint请直接填写域名")
    if not config.Max_Retries:
        logger.critical("无法找到Max_Retries参数")
        raise ValueError("无法找到Max_Retries参数")
    return True


if __name__ == "__main__":

    logger.setLevel(config.LogLevel)
    formatter = logging.Formatter(config.LogFormat)
    chlr = logging.StreamHandler()
    chlr.setFormatter(formatter)
    logger.addHandler(chlr)

    parser = argparse.ArgumentParser()
    parser.add_argument('--check_configs', action='store_true', help='执行check_configs')
    parser.add_argument('--kms_sk', help='以参数的形式输入KMS服务的SK')
    parser_group = parser.add_mutually_exclusive_group()
    parser_group.add_argument('-d', help='下载文件', nargs=2, type=str, metavar=('Remote_File', 'Local_File'), dest='download_file')
    parser_group.add_argument('-u', help='上传文件', nargs=2, type=str, metavar=('Local_File', 'Remote_File'), dest='upload_file')

    args = parser.parse_args()

    if args.check_configs:
        check_configs()
    print(args)
    r_oss = OssOperation(args.kms_sk)

    if args.download_file:
        print(r_oss.download_and_decrypt_file(args.download_file[1], args.download_file[0]))
    if args.upload_file:
        print(r_oss.encrypt_and_upload_files(args.upload_file[0], args.upload_file[1]))
