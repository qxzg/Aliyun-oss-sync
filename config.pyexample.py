OSSAccessKeyId = ""  # OSS服务用户AK
OSSAccessKeySecret = ""  # OSS服务用户SK
OssEndpoint = ""  # OSS Endpoint
bucket_name = ""  # OSS Bucket名称
default_storage_class = "Archive"  # Object的存储类型，取值：Standard、IA、Archive和ColdArchive

local_base_dir = "/mnt/"  # 本地工作目录（绝对路径, eg：/mnt/）
remote_base_dir = "nas-backup/"  # 上传至OSS时的路径前缀
backup_dirs = ["personal/", "www/nextcloud/data/"]  # 备份目录（相对于local_base_dir, eg:data/）
backup_exclude = ['personal/path/to/exclude']  # 相对路径，以Unix 文件名模式匹配（大小写敏感）
temp_dir = "/tmp/oss-sync/"  # 临时文件位置，绝对路径
Max_Retries = 5  # 遇到网络错误时最大重试次数

LogFile = "/root/oss-sync.log"  # 日志文件位置，推荐使用绝对路径
LogLevel = "INFO"  # 日志级别，取值：DEBUG，INFO，WARNING，ERROR，CRITICAL
LogFormat = "%(asctime)s %(name)s - [%(levelname)s]: %(message)s"  # 日志输出格式

SCT_Send_Key = ""  # Server酱·Turbo推送密钥 （可选填）

# 在计算文件哈希值时允许一次性打开的最大文件大小(MB)，提高此参数可以加快大文件的计算速度，但是会增加内存消耗
MaxMemoryUsageAllow = (1024 * 1024) * 1024

Encrypted_Filename_With_Sha256 = False

passphrase = None  # 本地RSA公钥私钥密码
private_key = '''-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC6eT+L17XZNl1J
7Uyta76n1W7uP5HmZFssL+P4QvcSGCY0fes/1d+CGlaHxgwko8XccFJTlP1PWtpR
X6wUoDETabr+B2in6GRVPVvpYjekgcB7BKRXln4L2Bwa7n9VeBulTdtpo+tFEZbo
YC4vNet9W8EpDFAMyrceKoy3vvWiwX0MTtIO34rWB0cF5wDd5ajzdTvf4e80+RTf
wjOoAovzazvKmcEyoZqrWa0TB24s9pWcdf4SGks4AVZlggvk0yatQFzEbR2oKDQe
tdHdCaz/dD4xXEPuap9rKKof79G48nHzk/KWe+eWmDCU/erwZvLRej2fBfvJhX+U
u+puMsSxAgMBAAECggEBAJNZulA73XPOFLuVK3EiYd7ntifHzfe7t5vcIA2OhQQk
VxRFqD6iN2LsgxH4+qF9VJ2TmEp5wg0R4tBIhIcr6nvHob6YhiegaKA+w0FRnlx9
N2c+TMr1nZaoZ9UUP0R/i4D9W/NHV2MVuiTX08b0mahOd/2CwELLcRYCU33jBOFd
IJhDqJxBfr0Ut4rEhdyy2RCZf5XQwW4vT2xGqlLQ0zJwxjBJ3t3/yQM0Jrao1ERD
bJ+gwI2hCoh7IZZGvFU5Tx8QfJUwijoTdJ6uGB3DeH3GeS0bcvKyOXeWx/KM3s6r
OQVQMICeMRmJgLVabNaCRV/UinypmcJcDcyqHOrpDH0CgYEA37MpqBZyGJmHKUaH
Bf1QnMfucEzAPZ297JS7tH9Fiv0citcgE6EqBee+RFxtROdyCpmO/mvKpcdHRP85
9GAvRbaH7EFFBZtZQZU9P/6726WgNGTD8BBznw2thDSojP+5y9FR3EPTDFprFXdf
SNQ6cbReWBHt2VThhwFqmX19H5MCgYEA1WYOTn9AUtai0z1GsluLPwAB9lK0HSIS
E0p56luTIPgHHl8L9cp13uOp6cUGLZ3EfEjwASVFxgyDL9QhbpraLzb5ysEcV3M4
iI0qQPJkCCV9D4pce8JL0/1mvo6zYJENOnNhzK7g+/siRh0Lqs+FqGXXLY37z+wM
Jpqp8nacDSsCgYBdUvRlAIA3DQ3bRWYdNJIF5k7uIMburblHUsGASrxrgK8AqUDj
j4/liMnS4TBg16G3FFsYf0W6pYlxGn1GGz59een4wT4XWbkB6E32PcKHnvBYC1XG
+EYUK/OgvQs4T5NmmXvqRY1tkOctvHBPBOMg/puBaHFvAr9XwFqFkFm76wKBgGNe
O2k3/gbU5UsB7Iqe8A8s/Lzrs+0g8VPESVLkw3UFqaLt1U7lsM9SKcuuL/tLzLOm
7wNJjNz09J1v5QVw3ApCSjysgXsDLx7+xN8rP4M/maWD4x7J0a9r/sza/BIKWSOP
mMnL4P3U6hfF7KnkKjPJAFK5G7mtC9dqC5rYuj+zAoGACftg3kbfZf+F8w3fP1GL
vRr+cKUCaE0+C9BZOe8P3gPh87ex7pDsRI8YUBY39Dlp9rjIYIi/pRuubudq5uUv
lNidXmBLof0uAkzzMSmhPSlu4honnVkVY00TkZZr8j6mqFiV1mILLQ2ELsBZ+VQ9
JWUrmnilytPr7f4zprz1BYk=
-----END PRIVATE KEY-----
'''
public_key = '''-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAunk/i9e12TZdSe1MrWu+
p9Vu7j+R5mRbLC/j+EL3EhgmNH3rP9XfghpWh8YMJKPF3HBSU5T9T1raUV+sFKAx
E2m6/gdop+hkVT1b6WI3pIHAewSkV5Z+C9gcGu5/VXgbpU3baaPrRRGW6GAuLzXr
fVvBKQxQDMq3HiqMt771osF9DE7SDt+K1gdHBecA3eWo83U73+HvNPkU38IzqAKL
82s7ypnBMqGaq1mtEwduLPaVnHX+EhpLOAFWZYIL5NMmrUBcxG0dqCg0HrXR3Qms
/3Q+MVxD7mqfayiqH+/RuPJx85PylnvnlpgwlP3q8Gby0Xo9nwX7yYV/lLvqbjLE
sQIDAQAB
-----END PUBLIC KEY-----
'''
