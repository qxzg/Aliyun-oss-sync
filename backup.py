# -*- coding: utf-8 -*-
import argparse
import json
import logging
import os
import time
from fnmatch import fnmatchcase

import oss2
from rich.progress import (BarColumn, Progress, TextColumn,
                           TimeElapsedColumn)

from oss_sync_libs import (Colored, FileCount, OssOperation, bytes_to_str, calculate_local_file_sha256, check_configs, sct_push)

try:
    import config
except ModuleNotFoundError:
    raise Exception("无法找到config.py")

logger = logging.getLogger("backup")


def create_logger(no_file_logger: bool = False):
    global logger
    logger.setLevel(config.LogLevel)
    formatter = logging.Formatter(config.LogFormat)
    chlr = logging.StreamHandler()
    chlr.setFormatter(formatter)
    logger.addHandler(chlr)
    if not no_file_logger:
        try:
            fhlr = logging.FileHandler(filename=config.LogFile, encoding='utf-8')  # only work on python>=3.9
        except ValueError:
            fhlr = logging.FileHandler(filename=config.LogFile)
        fhlr.setFormatter(formatter)
        logger.addHandler(fhlr)


def sha256_to_path(__sha256: str) -> str:
    """将sha256字符串转换为目录结构
    """
    if len(__sha256) != 64:
        logger.error("[sha256_to_path]不正确的输入\"%s\"" % str(__sha256))
        raise ValueError
    __str_list = list(__sha256)
    __str_list.insert(1, "/")
    __str_list.insert(5, "/")
    return "".join(__str_list)


def is_dir_excluded(_dir: str) -> bool:
    """如果目录在排除列表中则返回True，反之返回False
    """
    for exclude_dir in config.backup_exclude:
        if fnmatchcase(_dir, exclude_dir):
            return True
    return False


def scan_backup_dirs() -> dict:
    """扫描备份目录
    """
    global logger
    local_files_to_sha256 = {}
    oss_waste_size = total_file_size = 0
    oss_block_size = 1024 * 64
    for backup_dirs in config.backup_dirs:
        logger.info("正在读取备份目录:" + backup_dirs)
        for root, dirs, files in os.walk(backup_dirs):
            for file_path in files:
                relative_path = os.path.join(root, file_path)  # 合成相对于local_base_dir的路径
                if is_dir_excluded(relative_path) or file_path == '.DS_Store' or os.path.islink(relative_path):
                    continue
                file_size = os.path.getsize(relative_path)
                if file_size == 0:
                    continue  # 排除文件大小为0的空文件
                local_files_to_sha256[relative_path] = ""
                total_file_size += file_size
                if file_size < oss_block_size:
                    oss_waste_size += oss_block_size - file_size
    logger.info("备份文件扫描完成\n备份文件总数：%s\n备份文件总大小：%s\n实际占用OSS大小：%s\n浪费的OSS容量：%s\n存储类型为：%s\n是否加密文件名：%s" %
                (color.red(len(local_files_to_sha256)), color.red(bytes_to_str(total_file_size)), color.red(bytes_to_str(oss_waste_size + total_file_size)),
                 color.red(bytes_to_str(oss_waste_size)), color.red(config.default_storage_class), color.red(config.Encrypted_Filename_With_Sha256)))
    return local_files_to_sha256


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--compare_sha256_before_uploading', action='store_true', help='添加此选项将会在上传文件前对比远端Object Header中的sha256，如相同则会跳过上传。适用于远端index不再可靠时')
    parser.add_argument('--rsa_passphrase', help='RSA私钥密码')
    parser.add_argument('--no_file_logger', action='store_true', help='不将日志写入文件')
    args = parser.parse_args()

    create_logger(args.no_file_logger)
    check_configs()
    color = Colored()
    oss = OssOperation(rsa_passphrase=args.rsa_passphrase)
    local_json_filename = config.temp_dir + config.remote_base_dir[:-1] + "sha256_local_index.json"
    remote_json_filename = config.temp_dir + config.remote_base_dir[:-1] + "sha256_remote_index.json"
    os.chdir(config.local_base_dir)

    ######################################################################

    start_time = time.time()
    # 扫描备份目录，获取文件列表
    local_files_sha256 = scan_backup_dirs()

    if not str(input("确认继续请输入Y，否则输入N：")) in ['y', 'Y']:
        exit()

    with Progress(  # 初始化进度条
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
        json_on_oss = "index/%s.json" % config.remote_base_dir[:-1]
        req = oss.download_and_decrypt_file(remote_json_filename, json_on_oss)
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
        for path in list(local_files_sha256):
            if i >= 2500:
                time.sleep(30)
                i = 0
            progress.update(task, description="[red]正在计算哈希", advance=1, filename=path)
            sha256 = calculate_local_file_sha256(path)
            progress.update(task, description="[red]正在上传文件")
            if not sha256:  # 计算sha256时出错，跳过该文件
                del (local_files_sha256[path])
                logger.warning("上传时无法找到文件%s，可能是由于文件被删除" % path)
                continue
            local_files_sha256[path] = sha256

            if not config.Encrypted_Filename_With_Sha256:
                if path in remote_files_sha256:
                    if remote_files_sha256[path] == sha256:  # 如果远端同名文件的sha256相同则跳过
                        continue
                    elif sha256 in sha256_to_remote_file:  # 如果远端存在同sha256文件则将本文件加入copy_list
                        copy_list[config.remote_base_dir + path] = config.remote_base_dir + sha256_to_remote_file[sha256]
                    else:  # 上传文件并覆盖
                        i += 1
                        try:
                            oss.encrypt_and_upload_files(path, config.remote_base_dir + path, storage_class=config.default_storage_class,
                                                         file_sha256=sha256, compare_sha256_before_uploading=args.compare_sha256_before_uploading)
                        except FileNotFoundError:
                            logger.warning("上传时无法找到文件%s" % path)
                            del (local_files_sha256[path])
                        except oss2.exceptions.RequestError:
                            logger.warning("由于网络错误无法上传文件%s" % path)
                            del (local_files_sha256[path])
                        else:
                            upload_list.append(path)
                            uploaded_file_size += os.path.getsize(path)
                elif sha256 in sha256_to_remote_file:
                    copy_list[config.remote_base_dir + path] = config.remote_base_dir + sha256_to_remote_file[sha256]
                else:  # 上传新增文件
                    i += 1
                    try:
                        oss.encrypt_and_upload_files(path, config.remote_base_dir + path, storage_class=config.default_storage_class,
                                                     file_sha256=sha256, compare_sha256_before_uploading=args.compare_sha256_before_uploading)
                    except FileNotFoundError:
                        logger.warning("上传时无法找到文件%s" % path)
                        del (local_files_sha256[path])
                    except oss2.exceptions.RequestError:
                        logger.warning("由于网络错误无法上传文件%s" % path)
                        del (local_files_sha256[path])
                    else:
                        upload_list.append(path)
                        uploaded_file_size += os.path.getsize(path)

            elif sha256 not in sha256_to_remote_file:
                i += 1
                remote_filename = sha256
                try:
                    oss.encrypt_and_upload_files(path, config.remote_base_dir + sha256_to_path(sha256), storage_class=config.default_storage_class,
                                                 file_sha256=sha256)
                except FileNotFoundError:
                    logger.warning("上传时无法找到文件%s" % path)
                    del (local_files_sha256[path])
                except oss2.exceptions.RequestError:
                    logger.warning("由于网络错误无法上传文件%s" % path)
                    del (local_files_sha256[path])
                else:
                    upload_list.append(path)
                    uploaded_file_size += os.path.getsize(path)
                    sha256_to_remote_file[sha256] = sha256_to_path(sha256)

    if len(copy_list) != 0:
        total_size_to_be_copied = 0.0
        src_obj_list = []
        remote_prefix_length = len(config.remote_base_dir)
        for dst_obj, src_obj in copy_list.items():
            if src_obj not in src_obj_list:
                src_obj_list.append(src_obj)
                total_size_to_be_copied += oss.get_remote_file_size(src_obj)

        if config.stored_in_DeepColdArchive:
            logger.info("后续通过生命周期将存储类型沉降为DeepColdArchive，直接进行上传操作")
            for dst_obj, src_obj in copy_list.items():
                try:
                    oss.encrypt_and_upload_files(dst_obj[remote_prefix_length:], dst_obj, storage_class=config.default_storage_class)
                except FileNotFoundError:
                    logger.warning("上传时无法找到文件%s" % dst_obj[remote_prefix_length:])
                    del (local_files_sha256[dst_obj[remote_prefix_length:]])
                except oss2.exceptions.RequestError:
                    logger.warning("由于网络错误无法上传文件%s" % dst_obj[remote_prefix_length:])
                    del (local_files_sha256[dst_obj[remote_prefix_length:]])
        elif config.default_storage_class == oss2.BUCKET_STORAGE_CLASS_COLD_ARCHIVE and total_size_to_be_copied <= config.skip_restore_if_copied_file_is_less:
            logger.info("当前需要复制%s文件，小于%s，自动启动上传操作" % (bytes_to_str(total_size_to_be_copied), bytes_to_str(config.skip_restore_if_copied_file_is_less)))
            for dst_obj, src_obj in copy_list.items():
                try:
                    oss.encrypt_and_upload_files(dst_obj[remote_prefix_length:], dst_obj, storage_class=config.default_storage_class)
                except FileNotFoundError:
                    logger.warning("上传时无法找到文件%s" % dst_obj[remote_prefix_length:])
                    del (local_files_sha256[dst_obj[remote_prefix_length:]])
                except oss2.exceptions.RequestError:
                    logger.warning("由于网络错误无法上传文件%s" % dst_obj[remote_prefix_length:])
                    del (local_files_sha256[dst_obj[remote_prefix_length:]])
        elif config.default_storage_class == oss2.BUCKET_STORAGE_CLASS_COLD_ARCHIVE and total_size_to_be_copied > config.skip_restore_if_copied_file_is_less:
            total_size_to_be_copied_GB = total_size_to_be_copied / (1024*1024*1024)
            plan_description = "\n总共需要复制%s文件。请输入对应的数字以选择处理方案：" \
                               "\n0. 不复制，直接从本地进行上传。预计耗时：%s（以30Mbps上传速度计算）| %s（以100Mbps上传速度计算）"\
                               "\n1. 使用高优先级解冻文件（耗时：1小时），然后再复制。\n\t预计耗费：%.3f元"\
                               "\n2. 使用批量先级解冻文件（耗时：2~5小时），然后再复制。\n\t预计耗费：%.3f元"\
                               "\n3. 使用标准先级解冻文件（耗时：5~12小时），然后再复制。\n\t预计耗费：%.3f元" % \
                               (bytes_to_str(total_size_to_be_copied),
                                time.strftime("%H时%M分%S秒", time.gmtime(total_size_to_be_copied / (1024 * 128 * 30))),
                                time.strftime("%H时%M分%S秒", time.gmtime(total_size_to_be_copied / (1024 * 128 * 100))),
                                (len(src_obj_list) * 0.003 + total_size_to_be_copied_GB * 0.2),
                                (len(src_obj_list) * 0.0003 + total_size_to_be_copied_GB * 0.06),
                                (len(src_obj_list) * 0.00003 + total_size_to_be_copied_GB * 0.03))
            sct_push('[OSS-Sync]请选择文件复制方案', plan_description.replace('\n', '  \n'))
            logger.info(plan_description)
            while True:
                plan_number = eval(input("请输入方案编号："))
                if type(plan_number) != int or plan_number not in [0, 1, 2, 3]:
                    logger.warning("请输入正确的编号！")
                    continue
                if str(input('确认执行方案%d吗？输入Y以确认' % plan_number)) in ['y', 'Y']:
                    break
                else:
                    continue

            if plan_number == 0:
                for dst_obj, src_obj in copy_list.items():
                    try:
                        oss.encrypt_and_upload_files(dst_obj[remote_prefix_length:], dst_obj, storage_class=config.default_storage_class)
                    except FileNotFoundError:
                        logger.warning("上传时无法找到文件%s" % dst_obj[remote_prefix_length:])
                        del (local_files_sha256[dst_obj[remote_prefix_length:]])
                    except oss2.exceptions.RequestError:
                        logger.warning("由于网络错误无法上传文件%s" % dst_obj[remote_prefix_length:])
                        del (local_files_sha256[dst_obj[remote_prefix_length:]])
            else:
                for src_obj in src_obj_list:
                    oss.restore_remote_file(src_obj, restore_configuration=plan_number-1)
                if plan_number == 1:
                    time.sleep(3600)
                    delay = 30
                elif plan_number == 2:
                    time.sleep(3600*2)
                    delay = 60
                else:
                    time.sleep(3600*5)
                    delay = 120

                for src_obj in src_obj_list:
                    while oss.check_restore_status(src_obj) != 200:
                        time.sleep(delay)
                oss.copy_remote_files(copy_list, storage_class=config.default_storage_class)
            # https://help.aliyun.com/document_detail/51374.html#title-vi1-wio-4gv
            # https://www.aliyun.com/price/product#/oss/detail
        elif config.default_storage_class == oss2.BUCKET_STORAGE_CLASS_ARCHIVE:
            for src_obj in src_obj_list:
                oss.restore_remote_file(src_obj)
            time.sleep(90)
            while oss.check_restore_status(src_obj_list[-1]) == 200:
                time.sleep(10)
            oss.copy_remote_files(copy_list, storage_class=config.default_storage_class)
        else:
            oss.copy_remote_files(copy_list, storage_class=config.default_storage_class)

    delete_list = []  # 需要删除的文件列表
    if not config.Encrypted_Filename_With_Sha256:
        for path, sha256 in remote_files_sha256.items():
            if path not in local_files_sha256:
                delete_list.append(config.remote_base_dir + path)
    else:
        sha256_to_local_file = list(local_files_sha256.values())
        for sha256 in sha256_to_remote_file:
            if sha256 not in sha256_to_local_file:
                delete_list.append(config.remote_base_dir + sha256_to_path(sha256))
    if len(delete_list) != 0:
        oss.delete_remote_files(delete_list)

    try:
        with open(local_json_filename, 'w') as fobj:
            json.dump(local_files_sha256, fobj, separators=(',', ':'))
        logger.info("sha256成功保存到" + local_json_filename)
    except EnvironmentError:
        logger.exception("保存json文件时出错，无法保存至%s，尝试保存至%ssha256_local.json" % (local_json_filename, config.local_base_dir))
        with open(config.local_base_dir + "sha256_local.json", 'w') as fobj:
            json.dump(local_files_sha256, fobj, separators=(',', ':'))

    ######################################################################
    try:
        oss.encrypt_and_upload_files(local_json_filename, json_on_oss, storage_class='Standard', compare_sha256_before_uploading=True)
    except oss2.exceptions.RequestError:
        logger.warning("由于网络错误无法上传文件%s" % local_json_filename)

    if not config.Encrypted_Filename_With_Sha256:
        logger.info("已复制的文件列表:\n" + str(copy_list).replace("': '", "' <-- '"))
    logger.info("已删除的文件列表:\n" + str(delete_list))
    logger.info("已上传的文件列表:\n" + str(upload_list))
    total_time = time.strftime("%H:%M:%S", time.gmtime(time.time() - start_time))
    logger.info("\n复制的文件总数：%s\n删除的文件总数：%s\n上传的文件总数：%s\n上传的文件总大小：%s\n总耗时：%s" %
                (color.red(len(copy_list)), color.red(len(delete_list)), color.red(len(upload_list)), color.red(bytes_to_str(uploaded_file_size)), total_time))
    if config.SCT_Send_Key:
        sct_push("[OSS-Sync]上传完成", "#### 复制的文件总数：%d 个  \n#### 删除的文件总数：%d 个  \n#### 上传的文件总数：%d 个  \n#### 上传的文件总大小：%s  \n#### 总耗时：%s" %
                 (len(copy_list), len(delete_list), len(upload_list), bytes_to_str(uploaded_file_size), total_time))
