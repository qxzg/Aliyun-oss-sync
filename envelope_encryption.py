import sys
import json
from Crypto.Cipher import AES

from alibabacloud_kms20160120.client import Client as KmsClient
from alibabacloud_tea_openapi import models as OpenApiModels
from alibabacloud_kms20160120 import models as KmsModels

import config


api_config = OpenApiModels.Config(
    access_key_id=config.AccessKeyId,
    access_key_secret=config.AccessKeySecret,
    endpoint='kms.%s.aliyuncs.com' % (config.KMSRegion)
)
client = KmsClient(api_config)


def GenerateDataKey():
    """获取密钥

    API文档：https://help.aliyun.com/document_detail/28948.html

    Returns:
        dict:
        CiphertextBlob (str):数据密钥被指定CMK的主版本加密后的密文
        Plaintext (str):数据密钥的明文经过Base64编码的后的值
        KeyId (str):密钥ID
        KeyVersionId (str):密钥版本ID
        RequestId (str):请求ID
    """
    generate_data_key_request = KmsModels.GenerateDataKeyRequest(
        key_id=config.CMKID,
        key_spec='AES_256'
    )    
    return(client.generate_data_key(generate_data_key_request).to_map())


def DecryptDataKey(Ciphertext):
    """解密密文

    API文档：https://help.aliyun.com/document_detail/28950.html

    Args:
        Ciphertext (str): 已经过base64解码的，待解密的密文
    Returns:
        dict:
        Plaintext (str):解密后的明文
        KeyId' (str)
        KeyVersionId (str)
        RequestId (str)
    """
    decrypt_request=KmsModels.DecryptRequest(
        ciphertext_blob=str(Ciphertext)
    )
    return(client.decrypt(decrypt_request).to_map())

if __name__ == '__main__':
    print(GenerateDataKey())