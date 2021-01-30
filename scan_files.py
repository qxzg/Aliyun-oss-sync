import hashlib
import logging
import os
import sys
import time
import traceback
import json
import threading

import config

MaxMemoryUsageAllow = (1024 * 1024) * 1024  # 在计算文件哈希值时允许一次性打开的最大文件大小(MB)，提高此参数可以加快大文件的计算速度，但是会增加内存消耗
LogFile = "oss-sync.log"
LogFormat = "%(asctime)s - [%(levelname)s]: %(message)s"

try:
    logging.basicConfig(filename=LogFile, encoding='utf-8', level=logging.DEBUG, format=LogFormat)  # only work on python>=3.9
except ValueError:
    logging.basicConfig(filename=LogFile, level=logging.DEBUG, format=LogFormat)
    logging.warning("Python版本小于3.9，logging将不会使用encoding参数")


def Calculate_File_sha256(file_name):
    """计算文件的sha256

    :param str file_name: 需要计算sha256的文件名
    """
    #start_time = time.time()
    m = hashlib.sha256()
    try:
        with open(file_name, 'rb') as fobj:
            if os.path.getsize(file_name) > MaxMemoryUsageAllow:
                while True:
                    data = fobj.read(MaxMemoryUsageAllow)
                    if not data:
                        break
                    m.update(data)
            else:
                m.update(fobj.read())
    except:
        logging.exception("Fail when opening the file: %s", file_name)
    #logging.debug("分块sha256 耗时 %f 秒" % (time.time() - start_time))
    return m.hexdigest()


def ListFiles(target_dir):
    paths = []
    file_num = 0
    file_size = 0
    target_dir = os.path.abspath(target_dir)
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            path = os.path.join(root, file)
            paths.append(path)  # 使用绝度路径以避免问题
            file_num += 1
            file_size += os.path.getsize(path)
    return [paths, file_num, file_size]


if __name__ == "__main__":

    try:
        os.chdir(config.local_bace_dir)
    except FileNotFoundError:
        print("本地工作目录'%s'无效，请检查设置" % config.local_bace_dir)
        logging.exception("本地工作目录'%s'无效，请检查设置" % config.local_bace_dir)
        sys.exit(1)
    try:
        for dirs in config.backup_dirs:
            assert os.path.isdir(dirs)
    except AssertionError:
        print("备份目录'%s'无效，请检查设置" % dirs)
        logging.exception("备份目录'%s'无效，请检查设置" % dirs)
        sys.exit(1)


    start_time = time.time()
    files = {}
    file_num = 0
    file_size = 0
    for i in config.backup_dirs:
        logging.info("正在读取备份目录:" + i)
        getfiles = ListFiles(i)
        for path in getfiles[0]:
            files[path] = ""
        file_num += getfiles[1]
        file_size += getfiles[2]
    del getfiles

    logging.info("备份文件扫描完成\n备份文件总数：%d\n备份文件总大小：%.2f GB" % (file_num, file_size / (1024 * 1024 * 1024)))
    logging.info("开始计算sha256")

    for path in files:  # TODO: 实现多线程计算sha256
        files[path] = Calculate_File_sha256(path)
    with open('/root/sha256.json', 'w') as json_file:
        json.dump(files, json_file)
    logging.info("共耗时 %f 秒" % (time.time() - start_time))
