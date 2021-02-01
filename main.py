# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import os
import sys
import time

import config
import oss_sync_libs
"""
try:
    logging.basicConfig(filename=config.LogFile, encoding='utf-8', level=logging.DEBUG, format=config.LogFormat)  # only work on python>=3.9
except ValueError:
    logging.basicConfig(filename=config.LogFile, level=logging.DEBUG, format=config.LogFormat)
    logging.warning("Python版本小于3.9，logging将不会使用encoding参数")
"""
logging.basicConfig(level=logging.DEBUG, format=config.LogFormat)

def chaek_dir_configs():
    # 检查各参数合法性
    if config.local_bace_dir[0] != '/' or config.local_bace_dir[-1] != '/':
        logging.critical("本地工作目录(local_bace_dir)必须为带有前导和后导/的格式")
        raise Exception("本地工作目录(local_bace_dir)必须为带有前导和后导/的格式")
    if config.temp_dir[0] != '/' or config.temp_dir[-1] != '/':
        logging.critical("临时目录(temp_dir)必须为带有前导和后导/的格式")
        raise Exception("临时目录(temp_dir)必须为带有前导和后导/的格式")
    if config.remote_bace_dir[0] == '/' or config.remote_bace_dir[-1] != '/':
        logging.critical("远端工作目录(remote_bace_dir)必须为带有后导/的格式")
        raise Exception("远端工作目录(remote_bace_dir)必须为带有后导/的格式")
    for path in config.backup_dirs:
        if path[0] == '/' or path[-1] != '/':
            logging.critical("本地备份目录(backup_dirs)必须为带有后导/的格式")
            raise Exception("本地备份目录(backup_dirs)必须为带有后导/的格式")
    # 检查目录是否存在
    try:
        os.chdir(config.local_bace_dir)
    except FileNotFoundError:
        logging.exception("本地工作目录'%s'无效，请检查设置" % config.local_bace_dir)
        raise Exception("本地工作目录'%s'无效，请检查设置" % config.local_bace_dir)
    try:
        for dirs in config.backup_dirs:
            assert os.path.isdir(dirs)
    except AssertionError:
        logging.exception("备份目录'%s'无效，请检查设置" % dirs)
        raise Exception("备份目录'%s'无效，请检查设置" % dirs)
    if not os.path.exists(config.temp_dir):
        logging.info("临时文件夹%s不存在")
        os.makedirs(config.temp_dir)


if __name__ == "__main__":

    chaek_dir_configs()
else:
    local_json_filename = config.temp_dir + "sha256_local.json"
######################################################################

    local_files_sha256 = {}  # 本地文件与sha256对应表
# 扫描备份目录，获取文件列表
    start_time = time.time()
    file_num = 0
    file_size = 0
    for backup_dirs in config.backup_dirs:
        logging.info("正在读取备份目录:" + backup_dirs)
        for root, dirs, files in os.walk(os.path.abspath(backup_dirs)):
            for file in files:
                absolut_path = os.path.join(root, file)  # 使用绝对路径
                local_files_sha256[absolut_path] = ""
                file_num += 1
                file_size += os.path.getsize(absolut_path)
    logging.info("备份文件扫描完成\n备份文件总数：%d\n备份文件总大小：%.2f GB" % (file_num, file_size / (1024 * 1024 * 1024)))
# 计算备份文件的sha256
    logging.info("开始计算sha256")
    for path in local_files_sha256:  # TODO: 实现多线程计算sha256  doc: https://www.liaoxuefeng.com/wiki/1016959663602400/1017628290184064
        local_files_sha256[path] = oss_sync_libs.Calculate_Local_File_sha256(path)
    try:
        with open(local_json_filename, 'w') as json_fileobj:
            json.dump(local_files_sha256, json_fileobj)
        logging.info("sha256计算完成，保存到" + local_json_filename)
    except:
        logging.exception("保存json文件时出错，无法保存至%s，尝试保存至%ssha256_local.json" % (local_json_filename, config.local_bace_dir))
        with open(config.local_bace_dir + "sha256_local.json", 'w') as json_fileobj:
            json.dump(local_files_sha256, json_fileobj)

######################################################################

    remote_files_sha256 = {}  # 远程文件与sha256对应表
    sha256_to_remote_file = {}  # sha256与远程文件对应表
# 获取远程文件json

    for file, sha256 in remote_files_sha256.items():
        sha256_to_remote_file[sha256] = file
