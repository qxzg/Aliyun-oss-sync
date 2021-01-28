import os
import hashlib
import logging
import os
import sys
import time
import traceback
import logging

MaxMemoryUsageAllow = (1024 * 1024) * 1024  # 在计算文件sha512时允许的最大内存消耗(MB)，提高此参数可以加快大文件的计算速度
LogFile = "oss-sync.log"
LogFormat = "[%(asctime)s] %(levelname)s: %(message)s"

local_bace_dir = "/mnt/"  # 本地工作目录（绝对路径, eg：/mnt/）
backup_dirs = ["asd/"]  # 备份目录（相对于local_bace_dir, eg:data/）

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

logging.basicConfig(filename=LogFile, encoding='utf-8', level=logging.DEBUG, format='[%(asctime)s] %(levelname)s: %(message)s')


def get_file_sha512(file_name):
    #start_time = time.time()
    m = hashlib.sha512()
    try:
        with open(file_name, 'rb') as fobj:
            if os.path.getsize(file_name) > MaxMemoryAllow:
                while True:
                    data = fobj.read(MaxMemoryAllow)
                    if not data:
                        break
                    m.update(data)
            else:
                m.update(fobj.read())
    except:
        logging.exception("Fail when opening the file: %s", file_name)
    #logging.debug("分块sha512 耗时 %f 秒" % (time.time() - start_time))
    return m.hexdigest()


def listFiles(dir):
    paths = []
    for root, dirs, files in os.walk(dir):
        for file in files:
            paths.append(os.path.abspath(os.path.join(root, file)))  # 使用绝度路径以避免问题
    return paths


if __name__ == "__main__":
    files = listFiles('D:\Python')
    start_time = time.time()
    for path in files:
        get_file_sha512(path)
    logging.debug("sha512 耗时 %f 秒" % (time.time() - start_time))
    # get_file_sha512('ll.asd')
