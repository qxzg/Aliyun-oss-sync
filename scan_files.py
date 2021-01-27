import os
import hashlib
import time
import traceback
import logging

MaxMemoryAllow = int(1024 * 1024 * 100)  # 在计算文件sha512时允许的最大内存消耗(MB)，提高此参数可以加快大文件的计算速度
LogFile = "oss-sync.log"

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
