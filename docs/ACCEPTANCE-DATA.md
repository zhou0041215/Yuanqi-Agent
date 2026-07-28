# 验收测试数据约定

自动化和人工验收创建的数据必须使用 `AT-` 或 `TEST-` 业务编号；会话、Trace 使用
`acceptance-` 前缀，通知标题使用 `[ACCEPTANCE]` 前缀。

测试完成后在非生产数据库执行 `scripts/cleanup-acceptance-data.sql`。脚本只删除上述命名空间，
不会删除内置开发账号、已发布医学知识或真实业务数据。生产环境禁止执行此脚本。
