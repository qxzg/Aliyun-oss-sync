# -*- coding: utf-8 -*-
# 客户端加密文档：https://help.aliyun.com/document_detail/74371.html
# 断点续传文档：https://help.aliyun.com/document_detail/88433.html
import os
import sqlite3
import oss2
from oss2.crypto import AliKMSProvider

import config

MultipartUpload_Min_Filesize = (1024 * 1024 * 1024) * 13 # 当文件大小大于该值时使用断点续传（GB）。不得大于5GB
assert MultipartUpload_Min_Filesize <= 1024 * 1024 * 1024 * 5, "断点续传启用大小必须小于5GB"

def get_content_length(data):
    length = len(data.keys()) * 2 - 1
    total = ''.join(list(data.keys()) + list(data.values()))
    length += len(total)
    return length


auth = oss2.Auth(config.AccessKeyId, config.AccessKeySecret)
kms_provider = AliKMSProvider(config.AccessKeyId, config.AccessKeySecret, config.KMSRegion, config.CMKID)
bucket = oss2.CryptoBucket(auth, config.OssEndpoint, config.bucket_name, crypto_provider=kms_provider)


key = 'motto.zip'
content = open(key, "rb")
filename = 'download.txt'
print(type(b'a' * 1024 * 1024))

# 上传文件。
bucket.put_object(key, content.read(), headers={'content-length': str(os.path.getsize(key))})

# 下载OSS文件到本地内存。
result = bucket.get_object(key)
# 下载OSS文件到本地文件。
result = bucket.get_object_to_file(key, filename)

# 验证获取到的文件内容跟上传时的文件内容是否一致。
content_got = b''
for chunk in result:
    content_got += chunk
assert content_got == content


# 验证获取到的文件内容跟上传时的文件内容是否一致。
with open(filename, 'rb') as fileobj:
    assert fileobj.read() == content
