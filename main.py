# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import os
import sys
import time
from getpass import getpass

import oss2

import config
import oss_sync_libs

logger = logging.getLogger("main")
logger.setLevel(config.LogLevel)
formatter = logging.Formatter(config.LogFormat)
chlr = logging.StreamHandler()
chlr.setFormatter(formatter)
try:
    fhlr = logging.FileHandler(filename=config.LogFile, encoding='utf-8')  # only work on python>=3.9
except ValueError:
    fhlr = logging.FileHandler(filename=config.LogFile)
fhlr.setFormatter(formatter)
del formatter
logger.addHandler(chlr)
logger.addHandler(fhlr)

if __name__ == "__main__":

    oss_sync_libs.chaek_configs()
    local_json_filename = config.temp_dir + "sha256_local.json"
    remote_json_filename = config.temp_dir + "sha256_remote.json"
    oss = oss_sync_libs.Oss_Operation(str(getpass("请输入AK为\"%s\"的KMS服务的SK：" % config.KMSAccessKeyId)))

######################################################################
# else
    local_files_sha256 = {}  # 本地文件与sha256对应表
# 扫描备份目录，获取文件列表
    start_time = time.time()
    totle_file_num = 0
    totle_file_size = 0
    oss_waste_size = 0
    if config.default_storage_class == "Standard":
        oss_block_size = 0
    else:
        oss_block_size = 1024 * 64
# else:
    for backup_dirs in config.backup_dirs:
        logger.info("正在读取备份目录:" + backup_dirs)
        for root, dirs, files in os.walk(backup_dirs):
            if root.startswith(config.backup_exclude):
                continue  # 排除特定文件夹
            for file in files:
                relative_path = os.path.join(root, file)  # 合成相对于local_bace_dir的路径
                file_size = os.path.getsize(relative_path)
                if file_size == 0:
                    continue  # 排除文件大小为0的空文件
                local_files_sha256[relative_path] = ""
                totle_file_num += 1
                totle_file_size += file_size
                if file_size < oss_block_size:
                    oss_waste_size += oss_block_size - file_size
    totle_file_size = totle_file_size / (1024 * 1024 * 1024)
    oss_waste_size = oss_waste_size / (1024 * 1024 * 1024)
    logger.info("备份文件扫描完成\n备份文件总数：%d\n备份文件总大小：%.2f GB\n实际占用OSS大小：%.2f GB\n浪费的OSS容量：%.2f GB\n存储类型为：%s" %
                (totle_file_num, totle_file_size, (oss_waste_size + totle_file_size), oss_waste_size, config.default_storage_class))
    if str(input("确认继续请输入Y，否则输入N：")) in ['y', 'Y']:
        exit()

    # 获取远程文件json
    oss.Download_Decrypted_File(remote_json_filename, "sha256.json")
    with open(remote_json_filename, 'r') as fobj:
        remote_files_sha256 = json.load(fobj)
    sha256_to_remote_file = {}  # sha256与远程文件对应表
    for file, sha256 in remote_files_sha256.items():
        sha256_to_remote_file[sha256] = file

# 计算备份文件的sha256
# else:
    copy_list = {}  # 需要复制的文件列表{目标文件: 源文件}
    uplode_list = []  # 需要上传的文件列表
    logger.info("开始上传文件")
    for path in local_files_sha256:  # TODO: 实现多线程计算sha256  doc: https://www.liaoxuefeng.com/wiki/1016959663602400/1017628290184064
        sha256 = oss_sync_libs.Calculate_Local_File_sha256(path)
        if sha256 == False:
            del(local_files_sha256[path])
            logger.warning("上传时无法找到文件%s，可能是由于文件被删除" % path)
            continue
        local_files_sha256[path] = sha256
        if path in remote_files_sha256:
            if remote_files_sha256[path] == sha256:
                continue
            elif sha256 in sha256_to_remote_file:
                copy_list[config.remote_bace_dir + path] = config.remote_bace_dir + sha256_to_remote_file[sha256]
            else:  # 上传文件并覆盖
                try:
                    oss.Uplode_File_Encrypted(path, config.remote_bace_dir + path, storage_class=config.default_storage_class,
                                              file_sha256=sha256, check_sha256_before_uplode=False)
                except FileNotFoundError:
                    logger.warning("上传时无法找到文件%s，可能是由于文件被删除" % path)
                    del(local_files_sha256[path])
                except oss2.exceptions.ClientError:
                    logger.warning("由于网络错误无法上传文件%s" % path)
                    del(local_files_sha256[path])
                else:
                    uplode_list.append(path)
        elif sha256 in sha256_to_remote_file:
            copy_list[config.remote_bace_dir + path] = config.remote_bace_dir + sha256_to_remote_file[sha256]
        else:  # 上传新增文件
            try:
                oss.Uplode_File_Encrypted(path, config.remote_bace_dir + path, storage_class=config.default_storage_class,
                                          file_sha256=sha256, check_sha256_before_uplode=False)
            except FileNotFoundError:
                logger.warning("上传时无法找到文件%s" % path)
                del(local_files_sha256[path])
            except oss2.exceptions.ClientError:
                logger.warning("由于网络错误无法上传文件%s" % path)
                del(local_files_sha256[path])
            else:
                uplode_list.append(path)

    if len(copy_list) != 0:
        processed = []
        for dst_obj, src_obj in copy_list.items():
            if src_obj not in processed:
                oss.Restore_Remote_File(src_obj)
                processed.append(src_obj)
        time.sleep(90)
        oss.Copy_remote_files(copy_list, storage_class=config.default_storage_class)
        del processed
    delete_list = []  # 需要删除的文件列表
    for path, sha256 in remote_files_sha256.items():
        if not path in local_files_sha256:
            delete_list.append(config.remote_bace_dir + path)
    if len(delete_list) != 0:
        oss.Delete_Remote_files(delete_list)

    try:
        with open(local_json_filename, 'w') as json_fileobj:
            json.dump(local_files_sha256, json_fileobj)
        logger.info("sha256保存到" + local_json_filename)
    except:
        logger.exception("保存json文件时出错，无法保存至%s，尝试保存至%ssha256_local.json" % (local_json_filename, config.local_bace_dir))
        with open(config.local_bace_dir + "sha256_local.json", 'w') as json_fileobj:
            json.dump(local_files_sha256, json_fileobj)

######################################################################
# else:

    with open(local_json_filename, 'w') as fobj:
        json.dump(local_files_sha256, fobj)
    oss.Uplode_File_Encrypted(local_json_filename, 'sha256.json', storage_class='Standard')
    logger.info("已复制的文件列表:\n" + str(copy_list).replace("': '", "' <-- '"))
    logger.info("已删除的文件列表:\n" + str(delete_list))
    logger.info("已上传的文件列表:\n" + str(uplode_list))
    uplode_file_size = 0.0
    for path in uplode_list:
        uplode_file_size += os.path.getsize(path)
    logger.info("\n复制的文件总数：%d\n删除的文件总数：%d\n上传的文件总数：%d\n上传的文件总大小：%.2f GB" %
                (len(copy_list), len(delete_list), len(uplode_list), uplode_file_size / (1024 * 1024 * 1024)))
