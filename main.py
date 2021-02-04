# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import os
import sys
import time

import config
import oss_sync_libs

try:
    logging.basicConfig(filename=config.LogFile, encoding='utf-8', level=config.LogLevel, format=config.LogFormat)  # only work on python>=3.9
except ValueError:
    logging.basicConfig(filename=config.LogFile, level=config.LogLevel, format=config.LogFormat)


if __name__ == "__main__":

    oss_sync_libs.chaek_configs()
    local_json_filename = config.temp_dir + "sha256_local.json"
    remote_json_filename = config.temp_dir + "sha256_remote.json"

######################################################################
# else
    local_files_sha256 = {}  # 本地文件与sha256对应表
# 扫描备份目录，获取文件列表
    start_time = time.time()
    totle_file_num = 0
    totle_file_size = 0
# else:
    for backup_dirs in config.backup_dirs:
        logging.info("正在读取备份目录:" + backup_dirs)
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
    logging.info("备份文件扫描完成\n备份文件总数：%d\n备份文件总大小：%.2f GB" % (totle_file_num, totle_file_size / (1024 * 1024 * 1024)))
# 计算备份文件的sha256
# else:
    logging.info("开始计算sha256")
    for path in local_files_sha256:  # TODO: 实现多线程计算sha256  doc: https://www.liaoxuefeng.com/wiki/1016959663602400/1017628290184064
        sha256 = oss_sync_libs.Calculate_Local_File_sha256(path)
        if sha256 != False:
            local_files_sha256[path] = sha256
        else:
            del(local_files_sha256[path])
    try:
        with open(local_json_filename, 'w') as json_fileobj:
            json.dump(local_files_sha256, json_fileobj)
        logging.info("sha256计算完成，保存到" + local_json_filename)
    except:
        logging.exception("保存json文件时出错，无法保存至%s，尝试保存至%ssha256_local.json" % (local_json_filename, config.local_bace_dir))
        with open(config.local_bace_dir + "sha256_local.json", 'w') as json_fileobj:
            json.dump(local_files_sha256, json_fileobj)

######################################################################
# else:
    oss = oss_sync_libs.Oss_Operation()
    # 获取远程文件json
    oss.Download_Decrypted_File(remote_json_filename, "sha256.json")
    with open(remote_json_filename, 'r') as fobj:
        remote_files_sha256 = json.load(fobj)
    sha256_to_remote_file = {}  # sha256与远程文件对应表
    for file, sha256 in remote_files_sha256.items():
        sha256_to_remote_file[sha256] = file

    copy_list = {}  # 需要复制的文件列表{目标文件: 源文件}
    delete_list = []  # 需要删除的文件列表
    uplode_list = []  # 需要上传的文件列表
    with open(local_json_filename, 'r') as fobj:  # Dev!!
        local_files_sha256 = json.load(fobj)

    for item, sha256 in local_files_sha256.items():
        if item in remote_files_sha256:
            if remote_files_sha256[item] == sha256:
                continue
            elif sha256 in sha256_to_remote_file:
                copy_list[config.remote_bace_dir + item] = config.remote_bace_dir + sha256_to_remote_file[sha256]
            else:
                uplode_list.append(item)
        elif sha256 in sha256_to_remote_file:
            copy_list[config.remote_bace_dir + item] = config.remote_bace_dir + sha256_to_remote_file[sha256]
        else:
            uplode_list.append(item)
    for item, sha256 in remote_files_sha256.items():
        if not item in local_files_sha256:
            delete_list.append(config.remote_bace_dir + item)
    logging.info("开始同步远程文件")
    if len(copy_list) != 0:
        oss.Copy_remote_files(copy_list)
    if len(delete_list) != 0:
        oss.Delete_Remote_files(delete_list)
    if len(uplode_list) != 0:
        for file in uplode_list:
            try:
                oss.Uplode_File_Encrypted(file, config.remote_bace_dir + file, storage_class=config.default_storage_class, file_sha256=local_files_sha256[file])
            except FileNotFoundError:
                logging.warning("上传时无法找到文件%s" % file)
                del(local_files_sha256[file])
                uplode_list.remove(file)
    with open(local_json_filename, 'w') as fobj:
        json.dump(local_files_sha256, fobj)
    oss.Uplode_File_Encrypted(local_json_filename, 'sha256.json', storage_class='Standard')
    logging.info("copy_list:\n" + str(copy_list))
    logging.info("delete_list:\n" + delete_list)
    logging.info("uplode_list:\n" + uplode_list)
