"""
将 disease-kb 的 medical.json 导入 Neo4j

数据来源: https://github.com/nuolade/disease-kb
格式: JSONL，每行一个疾病 JSON 对象

实体类型: Disease(疾病), Drug(药品), Exam(检查), Department(科室), Symptom(症状),
          Food(食物), Therapy(治疗方式)
关系类型: HAS_SYMPTOM, TREATED_BY, REQUIRES_EXAM, BELONGS_TO, COMPLICATION,
          HAS_THERAPY, RECOMMENDED_EAT(宜吃), AVOID_EAT(忌吃), RECOMMENDED_RECIPE(推荐食谱)

说明: 早期版本会解析 do_eat/not_eat/recommand_eat/cure_way 以及疾病的
category/yibao_status/cost_money/get_prob/get_way/drug_detail，但从未写入
Neo4j。本脚本把这些此前被静默丢弃的数据全部接回。
"""

from __future__ import annotations

import json
import sys

from neo4j import GraphDatabase


def import_data(filepath: str, uri: str, user: str, password: str, database: str) -> None:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        driver.verify_connectivity()
        print("[OK] Neo4j connected")
    except Exception as e:
        print(f"[ERR] Neo4j connection failed: {e}")
        sys.exit(1)

    # Parse JSONL
    diseases = []
    drugs = set()
    foods = set()
    checks = set()
    departments = set()
    symptoms = set()
    cures = set()

    rels_symptom = []
    rels_common_drug = []
    rels_recommand_drug = []
    rels_check = []
    rels_department = []
    rels_acompany = []
    rels_cure_way = []
    rels_do_eat = []
    rels_no_eat = []
    rels_recommand_eat = []

    print(f"[*] Reading {filepath} ...")
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            name = data.get("name", "").strip()
            if not name:
                continue

            category = data.get("category", [])
            if not isinstance(category, list):
                category = [category] if category else []
            drug_detail = [
                x.strip()
                for x in (data.get("drug_detail", []) or [])
                if isinstance(x, str) and x.strip()
            ]
            disease_info = {
                "name": name,
                "desc": data.get("desc", ""),
                "cause": data.get("cause", ""),
                "prevent": data.get("prevent", ""),
                "easy_get": data.get("easy_get", ""),
                "cure_lasttime": data.get("cure_lasttime", ""),
                "cured_prob": data.get("cured_prob", ""),
                # 以下字段此前被解析忽略，现接回为 Disease 属性
                "category": [c.strip() for c in category if isinstance(c, str) and c.strip()],
                "yibao_status": (data.get("yibao_status") or "").strip(),
                "cost_money": (data.get("cost_money") or "").strip(),
                "get_prob": (data.get("get_prob") or "").strip(),
                "get_way": (data.get("get_way") or "").strip(),
                "drug_detail": drug_detail,
            }
            diseases.append(disease_info)

            for s in data.get("symptom", []):
                if s and s.strip():
                    symptoms.add(s.strip())
                    rels_symptom.append((name, s.strip()))

            for d in data.get("common_drug", []):
                if d and d.strip():
                    drugs.add(d.strip())
                    rels_common_drug.append((name, d.strip()))

            for d in data.get("recommand_drug", []):
                if d and d.strip():
                    drugs.add(d.strip())
                    rels_recommand_drug.append((name, d.strip()))

            for c in data.get("check", []):
                if c and c.strip():
                    checks.add(c.strip())
                    rels_check.append((name, c.strip()))

            dept = data.get("cure_department", [])
            if isinstance(dept, list):
                for d in dept:
                    if d and d.strip():
                        departments.add(d.strip())
                        rels_department.append((name, d.strip()))

            for c in data.get("cure_way", []):
                if c and c.strip():
                    cures.add(c.strip())
                    rels_cure_way.append((name, c.strip()))

            for a in data.get("acompany", []):
                if a and a.strip():
                    rels_acompany.append((name, a.strip()))

            for f in data.get("do_eat", []):
                if f and f.strip():
                    foods.add(f.strip())
                    rels_do_eat.append((name, f.strip()))

            for f in data.get("not_eat", []):
                if f and f.strip():
                    foods.add(f.strip())
                    rels_no_eat.append((name, f.strip()))

            for f in data.get("recommand_eat", []):
                if f and f.strip():
                    foods.add(f.strip())
                    rels_recommand_eat.append((name, f.strip()))

    print(f"    Diseases: {len(diseases)}")
    print(f"    Symptoms: {len(symptoms)}")
    print(f"    Drugs: {len(drugs)}")
    print(f"    Foods: {len(foods)}")
    print(f"    Checks: {len(checks)}")
    print(f"    Departments: {len(departments)}")
    print(f"    Cures: {len(cures)}")

    # Import to Neo4j
    batch_size = 1000
    with driver.session(database=database) as session:
        # Constraints
        print("[*] Creating constraints ...")
        for label in [
            "Disease", "Drug", "Exam", "Department", "Symptom", "Food", "Therapy",
        ]:
            session.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.name IS UNIQUE")

        # Disease nodes with properties (batched via UNWIND)
        print(f"[*] Importing {len(diseases)} diseases ...")
        for start in range(0, len(diseases), batch_size):
            session.run(
                """
                UNWIND $rows AS row
                MERGE (n:Disease {name: row.name})
                SET n.desc = row.desc, n.cause = row.cause, n.prevent = row.prevent,
                    n.easy_get = row.easy_get, n.cure_lasttime = row.cure_lasttime,
                    n.cured_prob = row.cured_prob,
                    n.category = row.category, n.yibao_status = row.yibao_status,
                    n.cost_money = row.cost_money, n.get_prob = row.get_prob,
                    n.get_way = row.get_way, n.drug_detail = row.drug_detail
                """,
                rows=diseases[start : start + batch_size],
            )
            print(f"    {min(start + batch_size, len(diseases))}/{len(diseases)}")

        # Other nodes (batched)
        for label, node_set in [
            ("Drug", drugs), ("Exam", checks),
            ("Department", departments), ("Symptom", symptoms),
            ("Food", foods), ("Therapy", cures),
        ]:
            names = list(node_set)
            print(f"[*] Importing {len(names)} {label} nodes ...")
            for start in range(0, len(names), batch_size):
                session.run(
                    f"UNWIND $names AS nm MERGE (n:{label} {{name: nm}})",
                    names=names[start : start + batch_size],
                )

        # Relationships (batched). Food/Therapy edges were previously dropped.
        rel_queries = [
            ("HAS_SYMPTOM", "Disease", "Symptom", rels_symptom),
            ("TREATED_BY", "Disease", "Drug", rels_common_drug + rels_recommand_drug),
            ("REQUIRES_EXAM", "Disease", "Exam", rels_check),
            ("BELONGS_TO", "Disease", "Department", rels_department),
            ("COMPLICATION", "Disease", "Disease", rels_acompany),
            ("HAS_THERAPY", "Disease", "Therapy", rels_cure_way),
            ("RECOMMENDED_EAT", "Disease", "Food", rels_do_eat),
            ("AVOID_EAT", "Disease", "Food", rels_no_eat),
            ("RECOMMENDED_RECIPE", "Disease", "Food", rels_recommand_eat),
        ]

        for rel_type, start_label, end_label, rels in rel_queries:
            pairs = [
                {"src": src, "tgt": tgt}
                for src, tgt in dict.fromkeys((s, t) for s, t in rels)
            ]
            print(f"[*] Creating {len(pairs)} {rel_type} relations ...")
            for start in range(0, len(pairs), batch_size):
                session.run(
                    f"""
                    UNWIND $pairs AS pair
                    MATCH (a:{start_label} {{name: pair.src}})
                    MATCH (b:{end_label} {{name: pair.tgt}})
                    MERGE (a)-[r:{rel_type}]->(b)
                    """,
                    pairs=pairs[start : start + batch_size],
                )

        # Stats
        print("\n[*] Final stats:")
        result = session.run("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY cnt DESC")
        for r in result:
            print(f"    {r['label']}: {r['cnt']}")
        result = session.run("MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS cnt ORDER BY cnt DESC")
        for r in result:
            print(f"    {r['type']}: {r['cnt']}")

    driver.close()
    print("\n[DONE] Import complete!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="data/medical.json")
    parser.add_argument("--uri", default="neo4j://localhost:17687")
    parser.add_argument("--user", default="neo4j")
    parser.add_argument("--password", default="yuanqi-local")
    parser.add_argument("--database", default="neo4j")
    args = parser.parse_args()
    import_data(args.file, args.uri, args.user, args.password, args.database)
