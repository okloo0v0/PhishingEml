# V1 数据归档

V1 是项目第一版基线数据工作区。`manifests/` 保存来源、清洗、去重、划分、训练和评测摘要；`processed/` 保存本地生成的大型数据与预测文件，默认不纳入 Git。

原始公开数据仍位于共享路径 `data/raw/`，本目录不重复复制原始文件。来源、许可、下载时间、大小和 SHA-256 见 `manifests/sources.csv`。该批数据包括 Nazario Phishing Corpus、SpamAssassin Public Corpus 以及 Zenodo 8339691 补充语料。

归档范围：V1.0 二分类基线，以及 V1.1 之前完成的清洗、去重和初始划分结果。不要将此目录下的历史产物作为 V1.2 的默认输入；V1.2 必须重新完成来源和活动级隔离。
