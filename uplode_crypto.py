# -*- coding: utf-8 -*-
# 客户端加密文档：https://help.aliyun.com/document_detail/74371.html
# 断点续传文档：https://help.aliyun.com/document_detail/88433.html
import os
import oss2
import hashlib
import logging
from oss2.crypto import AliKMSProvider
import hashlib
import config
from scan_files import Calculate_File_sha256

auth = oss2.Auth(config.AccessKeyId, config.AccessKeySecret)
kms_provider = AliKMSProvider(config.AccessKeyId, config.AccessKeySecret, config.KMSRegion, config.CMKID)
bucket = oss2.CryptoBucket(auth, config.OssEndpoint, config.bucket_name, crypto_provider=kms_provider)

uplode_file = "oss-sync.zip"
download_filename = 'download.zip'

try:
    logging.basicConfig(filename=LogFile, encoding='utf-8', level=logging.DEBUG, format=LogFormat)  # only work on python>=3.9
except ValueError:
    logging.basicConfig(filename=LogFile, level=logging.DEBUG, format=LogFormat)
    logging.warning("Python版本小于3.9，logging将不会使用encoding参数")

def Uplode_File_Encrypted(local_file_name, remote_file_name):
    org_file_sha256 = Calculate_File_sha256(uplode_file)  # TODO 从json获取文件sha256
    oss2.resumable_upload(
        bucket, remote_file_name, local_file_name,
        # store=oss2.ResumableStore(root='/tmp'),
        multipart_threshold=1024*1024*50,
        part_size=1024*1024*50,
        num_threads=4,
        headers={
            "content-length": str(os.path.getsize(uplode_file)),
            "x-oss-server-side-encryption": "KMS",
            "x-oss-storage-class": "IA",
            "x-oss-meta-sha256": org_file_sha256
        }
    )

def Download_Decrypted_File(local_file_name, remote_file_name):
    try:
        result = bucket.get_object_to_file(remote_file_name, local_file_name)
    except:
        logging.exception("无法从oss下载文件" + remote_file_name)
    return result

def Verify_Remote_File_Integrity(remote_file):
    result = bucket.get_object(remote_file)
    sha256 = hashlib.sha256()
    for chunk in result:
        sha256.update(chunk)
    print(result.headers)
    if sha256.hexdigest() == result.headers['x-oss-meta-sha256']:
        print("校验通过")
    else:
        print("数据不匹配")


if __name__ == "__main__":
    Uplode_File_Encrypted("sha256.json", )
    #Uplode_File_Encrypted(uplode_file)
    # 下载OSS文件到本地文件。
    #result = bucket.get_object_to_file(uplode_file, download_filename)
