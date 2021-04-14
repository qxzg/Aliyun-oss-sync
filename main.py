# -*- coding: utf-8 -*-
import json
import logging
import os
import time

import oss2
from rich.progress import (BarColumn, Progress, TextColumn,
                           TimeElapsedColumn)

from oss_sync_libs import (Calculate_Local_File_sha256, Chaek_Configs, Colored,
                           FileCount, OssOperation, SCT_Push, StrOfSize)

try:
    import config
except:
    raise Exception("无法找到config.py")

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

    color = Colored()
    Chaek_Configs()
    local_json_filename = config.temp_dir + "sha256_local.json"
    remote_json_filename = config.temp_dir + "sha256_remote.json"
    oss = OssOperation()

    ######################################################################

    local_files_sha256 = {}  # 本地文件与sha256对应表
    # 扫描备份目录，获取文件列表
    start_time = time.time()
    total_file_size = 0
    oss_waste_size = 0
    if config.default_storage_class == "Standard":
        oss_block_size = 0
    else:
        oss_block_size = 1024 * 64
    for backup_dirs in config.backup_dirs:
        logger.info("正在读取备份目录:" + backup_dirs)
        for root, dirs, files in os.walk(backup_dirs):
            if root.startswith(config.backup_exclude):
                continue  # 排除特定文件夹
            for file in files:
                relative_path = os.path.join(root, file)  # 合成相对于local_base_dir的路径
                file_size = os.path.getsize(relative_path)
                if file_size == 0:
                    continue  # 排除文件大小为0的空文件
                local_files_sha256[relative_path] = ""
                total_file_size += file_size
                if file_size < oss_block_size:
                    oss_waste_size += oss_block_size - file_size
    logger.info("备份文件扫描完成\n备份文件总数：%s\n备份文件总大小：%s\n实际占用OSS大小：%s\n浪费的OSS容量：%s\n存储类型为：%s" %
                (color.red(len(local_files_sha256)), color.red(StrOfSize(total_file_size)), color.red(StrOfSize(oss_waste_size + total_file_size)), color.red(StrOfSize(oss_waste_size)), color.red(config.default_storage_class)))
    if not str(input("确认继续请输入Y，否则输入N：")) in ['y', 'Y']:
        exit()

    with Progress(
            "[progress.percentage]{task.percentage:>3.2f}%",
            BarColumn(),
            FileCount(),
            "•",
            "[progress.elapsed]已用时间", TimeElapsedColumn(),
            "•",
            "[progress.description]{task.description}",
            TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
            ) as progress:
        task = progress.add_task("[red]正在准备上传...", total=len(local_files_sha256), start=False, filename="")

        # 获取远程文件json
        json_on_oss = "sha256/%s.json" % config.remote_base_dir[:-1]
        req = oss.Download_Decrypted_File(remote_json_filename, json_on_oss)
        if req == 200:
            with open(remote_json_filename, 'r') as fobj:
                remote_files_sha256 = json.load(fobj)
            sha256_to_remote_file = {}  # sha256与远程文件对应表
            for file, sha256 in remote_files_sha256.items():
                sha256_to_remote_file[sha256] = file
        elif req == 404:
            remote_files_sha256 = {}
            sha256_to_remote_file = {}

        # 计算备份文件的sha256
        copy_list = {}  # 需要复制的文件列表{目标文件: 源文件}
        upload_list = []  # 需要上传的文件列表
        uploaded_file_size = 0.0
        progress.start_task(task)
        i = 0
        for path in list(local_files_sha256):  # TODO: 实现多线程计算sha256  doc: https://www.liaoxuefeng.com/wiki/1016959663602400/1017628290184064
            if i >= 2500:
                time.sleep(30)
                i = 0
            progress.update(task, description="[red]正在计算哈希", advance=1, filename=path)
            sha256 = Calculate_Local_File_sha256(path)
            progress.update(task, description="[red]正在上传文件")
            if not sha256:
                del (local_files_sha256[path])
                logger.warning("上传时无法找到文件%s，可能是由于文件被删除" % path)
                continue
            local_files_sha256[path] = sha256
            if path in remote_files_sha256:
                if remote_files_sha256[path] == sha256:
                    continue
                elif sha256 in sha256_to_remote_file:
                    copy_list[config.remote_base_dir + path] = config.remote_base_dir + sha256_to_remote_file[sha256]
                else:  # 上传文件并覆盖
                    i += 1
                    try:
                        oss.Uplode_File_Encrypted(path, config.remote_base_dir + path, storage_class=config.default_storage_class,
                                                  file_sha256=sha256, check_sha256_before_uplode=False)
                    except FileNotFoundError:
                        logger.warning("上传时无法找到文件%s，可能是由于文件被删除" % path)
                        del (local_files_sha256[path])
                    except oss2.exceptions.RequestError:
                        logger.warning("由于网络错误无法上传文件%s" % path)
                        del (local_files_sha256[path])
                    else:
                        upload_list.append(path)
            elif sha256 in sha256_to_remote_file:
                copy_list[config.remote_base_dir + path] = config.remote_base_dir + sha256_to_remote_file[sha256]
            else:  # 上传新增文件
                i += 1
                try:
                    oss.Uplode_File_Encrypted(path, config.remote_base_dir + path, storage_class=config.default_storage_class,
                                              file_sha256=sha256, check_sha256_before_uplode=False)
                except FileNotFoundError:
                    logger.warning("上传时无法找到文件%s" % path)
                    del (local_files_sha256[path])
                except oss2.exceptions.RequestError:
                    logger.warning("由于网络错误无法上传文件%s" % path)
                    del (local_files_sha256[path])
                else:
                    upload_list.append(path)
                    uploaded_file_size += os.path.getsize(path)

    if len(copy_list) != 0:  # TODO 优化冷归档存储时复制文件的逻辑
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
        if path not in local_files_sha256:
            delete_list.append(config.remote_base_dir + path)
    if len(delete_list) != 0:
        oss.Delete_Remote_files(delete_list)

    try:
        with open(local_json_filename, 'w') as fobj:
            json.dump(local_files_sha256, fobj)
        logger.info("sha256保存到" + local_json_filename)
    except:
        logger.exception("保存json文件时出错，无法保存至%s，尝试保存至%ssha256_local.json" % (local_json_filename, config.local_base_dir))
        with open(config.local_base_dir + "sha256_local.json", 'w') as fobj:
            json.dump(local_files_sha256, fobj)

    ######################################################################

    with open(local_json_filename, 'w') as fobj:
        json.dump(local_files_sha256, fobj)
    oss.Uplode_File_Encrypted(local_json_filename, json_on_oss, storage_class='Standard')
    logger.info("已复制的文件列表:\n" + str(copy_list).replace("': '", "' <-- '"))
    logger.info("已删除的文件列表:\n" + str(delete_list))
    logger.info("已上传的文件列表:\n" + str(upload_list))
    total_time = time.strftime("%H:%M:%S", time.gmtime(time.time() - start_time))
    logger.info("\n复制的文件总数：%s\n删除的文件总数：%s\n上传的文件总数：%s\n上传的文件总大小：%s\n总耗时：%s" %
                (color.red(len(copy_list)), color.red(len(delete_list)), color.red(len(upload_list)), color.red(StrOfSize(uploaded_file_size)), total_time))
    if config.SCT_Send_Key:
        SCT_Push("[OSS-Sync]上传完成", "#### 复制的文件总数：%d 个  \n#### 删除的文件总数：%d 个  \n#### 上传的文件总数：%d 个  \n#### 上传的文件总大小：%s  \n#### 总耗时：%s" %
                 (len(copy_list), len(delete_list), len(upload_list), StrOfSize(uploaded_file_size), total_time))
