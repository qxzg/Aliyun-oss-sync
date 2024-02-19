# Aliyun-oss-sync

![GitHub](https://img.shields.io/github/license/qxzg/Aliyun-oss-sync)

----

### 使用方法：
挂载配置文件：/app/config.py
挂载备份目录：/mnt

----

update 2024.2.19:
- 阿里云推出深度冷归档存储类型`DeepColdArchive`，价格相比冷归档低1/2，为`0.0075 元/GB/月`，且取回费用`标准：1.67 元/万次+0.018 元/GB`也低于冷归档型的`批量：0.3 元/万次+0.03 元/GB`。 但是解冻时间更长：`标准48h/高优先级12h`。
- 深度冷归档类型的PUT调用费用高，为`3.5元/万次`，建议根据[深度冷归档存储使用最佳实践](https://help.aliyun.com/zh/oss/user-guide/deep-cold-archive-storage-usage-best-practices)以及`从标准、低频、归档沉降至深度冷归档，不会产生提前删除费用。`，先上传为归档型存储`Archive`，然后通过生命周期将Object的存储类型转换为深度冷归档存储。