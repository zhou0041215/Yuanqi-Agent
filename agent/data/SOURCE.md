# 医学图谱演示数据说明

本目录中的 `medical.json` 是用于本项目医学知识图谱导入和前端演示的**通用疾病目录**，不含患者、病历、处方、账号或其他个人信息。

## 来源与许可

- 上游项目：[`nuolade/disease-kb`](https://github.com/nuolade/disease-kb)
- 上游数据文件：`data/medical.json`
- 上游仓库声明的许可：Apache License 2.0；许可证副本见 [`LICENSE-disease-kb.txt`](LICENSE-disease-kb.txt)。
- 本项目保留了数据的原始 JSONL 格式；导入逻辑位于 [`../scripts/import_disease_kb.py`](../scripts/import_disease_kb.py)。

根据 Apache-2.0，本项目在保留来源、许可声明的前提下随源代码再分发该文件。上游 README 说明，该数据由公开医疗网站信息整理而来；数据权属、时效和医学准确性应由使用者自行核验。

## 使用边界

- 仅限学习、研发、图谱检索与产品演示，**不构成医疗建议、诊断、治疗或处方依据**。
- 生产使用前，应完成数据来源审查、内容校验、专业医疗审核及适用法律要求的评估。
- 请勿把患者信息、病历、处方、报告、密钥或数据库导出文件放入本目录；除 `medical.json` 和本说明外，其余 `agent/data/` 内容均被 Git 忽略。
