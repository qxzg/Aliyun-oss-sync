import hashlib
import logging
import os
import sys
import time
import traceback

MaxMemoryUsageAllow = (1024 * 1024) * 1024  # 在计算文件sha512时允许的最大内存消耗(MB)，提高此参数可以加快大文件的计算速度
LogFile = "oss-sync.log"
LogFormat = "%(asctime)s - [%(levelname)s]: %(message)s"

local_bace_dir = "/mnt/"  # 本地工作目录（绝对路径, eg：/mnt/）
backup_dirs = ["main-pool/personal/"]  # 备份目录（相对于local_bace_dir, eg:data/）

try:
    logging.basicConfig(filename=LogFile, encoding='utf-8', level=logging.DEBUG, format=LogFormat)  # only work on python>=3.9
except ValueError:
    logging.basicConfig(filename=LogFile, level=logging.DEBUG, format=LogFormat)
    logging.warning("Python版本小于3.9，logging将不会使用encoding参数")

try:
    os.chdir(local_bace_dir)
except FileNotFoundError:
    print("本地工作目录'%s'无效，请检查设置" % local_bace_dir)
    logging.exception("本地工作目录'%s'无效，请检查设置" % local_bace_dir)
    sys.exit(1)
try:
    for dirs in backup_dirs:
        assert os.path.isdir(dirs)
except AssertionError:
    print("备份目录'%s'无效，请检查设置" % dirs)
    logging.exception("备份目录'%s'无效，请检查设置" % dirs)
    sys.exit(1)


def Get_File_Sha1(file_name):
    """计算文件的sha1

    :param str file_name: 需要计算sha1的文件名
    """
    #start_time = time.time()
    m = hashlib.sha1()
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
    #logging.debug("分块sha1 耗时 %f 秒" % (time.time() - start_time))
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
    files = []
    file_num = 0
    file_size = 0
    for i in backup_dirs:
        print("正在读取备份目录:" + i)
        getfiles = ListFiles(i)
        files.append(getfiles[0])
        file_num += getfiles[1]
        file_size += getfiles[2]
    del getfiles
    print("备份文件总数：%d\n备份文件总大小：%.2f GB" % (file_num, file_size / (1024 * 1024 * 1024)))
"""
    start_time = time.time()
    file_sha1 = []
    for path in files:
        file_sha1.append(Get_File_Sha1(path))
    logging.debug("共扫描%d个文件 sha1 耗时 %f 秒" % (len(files), time.time() - start_time))
"""