# 全量疾病目录与科室治理

## 数据分层

系统把目录覆盖与医学事实审核分开处理：

- `Disease.catalogStatus = CATALOGED`：疾病名称可检索。
- `Symptom/Drug/Exam.catalogStatus = CATALOGED`：症状、药物和检查名称可检索。
- `Department.catalogStatus = STANDARDIZED`：科室名称已经标准化。
- `ROUTED_TO.evidenceLevel = REFERENCE_ONLY`：只用于初诊分流参考。
- 未发布的 `HAS_SYMPTOM`、`TREATED_BY`、`REQUIRES_EXAM` 和
  `COMPLICATION` 关系均标记为 `REFERENCE_ONLY`，只在知识图谱浏览页展示。
- `reviewStatus = PUBLISHED`：内容或关系通过发布审核，可作为医学事实展示。
- `catalogStatus = REJECTED`：无效源条目，不进入搜索和问答。
- `retrievalStatus = EXCLUDED`：命中版本化治理策略的已知污染实体，不进入
  GraphRAG 或向量索引；实体仍保留在 Neo4j 中供治理审计。

知识图谱浏览页可以查看完整目录关系，并用虚线和“目录资料·待审核”提示区分。
医学智能问答不会把这些候选关系当成可靠医学事实，不会据此生成诊断、处方或
治疗建议；只有正式发布的关系才能进入可信回答和向量索引。

## 科室标准

科室名称、代码和上级分类以国家卫生健康委员会《医疗机构诊疗科目名录》为
标准。医院习惯名称会映射到稳定名称，例如：

- 心内科 → 心血管内科
- 骨外科 → 骨科
- 传染科 → 感染科
- 儿科综合、小儿内科 → 儿科
- 普外科 → 普通外科

原名称和原关系不会删除，便于后续治理审计。

## 重复执行

```powershell
cd agent
.\.venv\Scripts\python.exe scripts\standardize_medical_catalog.py
```

脚本是幂等的：重复执行不会制造重复科室或重复分流关系。
脚本还会按
`agent/src/yuanqi_agent/resources/knowledge_governance.v1.json`
重新对账检索排除状态；规则删除后，旧排除标记会在下一次执行时被清理。

## 发布升级

目录关系不能自动升级为已审核医学知识。升级时必须补充权威 HTTPS 来源，
由审核人员确认疾病事实及关系，然后发布正式的 `BELONGS_TO`、`HAS_SYMPTOM`
等关系。Qdrant 继续只索引正式发布的知识文档，不索引目录候选。
