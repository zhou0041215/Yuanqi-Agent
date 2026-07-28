// Apply once with:
// cypher-shell -u neo4j -p <password> -f resources/neo4j-schema.cypher
//
// Neo4j stores shared medical reference knowledge only. Patient and other
// row-scoped business data stays in Java/MySQL and must never be copied here.

CREATE CONSTRAINT disease_name IF NOT EXISTS
FOR (node:Disease) REQUIRE node.name IS UNIQUE;

CREATE CONSTRAINT symptom_name IF NOT EXISTS
FOR (node:Symptom) REQUIRE node.name IS UNIQUE;

CREATE CONSTRAINT drug_name IF NOT EXISTS
FOR (node:Drug) REQUIRE node.name IS UNIQUE;

CREATE CONSTRAINT department_name IF NOT EXISTS
FOR (node:Department) REQUIRE node.name IS UNIQUE;

CREATE CONSTRAINT exam_name IF NOT EXISTS
FOR (node:Exam) REQUIRE node.name IS UNIQUE;

// Catalog-only reference entities imported from the open medical catalog.
// They never enter user-facing answers (see graph.py / medical_documents.py),
// only the knowledge-graph browse page.
CREATE CONSTRAINT food_name IF NOT EXISTS
FOR (node:Food) REQUIRE node.name IS UNIQUE;

CREATE CONSTRAINT therapy_name IF NOT EXISTS
FOR (node:Therapy) REQUIRE node.name IS UNIQUE;

CREATE TEXT INDEX disease_name_search IF NOT EXISTS
FOR (node:Disease) ON (node.name);

CREATE TEXT INDEX symptom_name_search IF NOT EXISTS
FOR (node:Symptom) ON (node.name);

CREATE TEXT INDEX drug_name_search IF NOT EXISTS
FOR (node:Drug) ON (node.name);

CREATE TEXT INDEX food_name_search IF NOT EXISTS
FOR (node:Food) ON (node.name);

// Governance lookups used by the catalog standardization and browse queries.
CREATE INDEX disease_catalog_status IF NOT EXISTS
FOR (node:Disease) ON (node.catalogStatus);

CREATE INDEX department_standard IF NOT EXISTS
FOR (node:Department) ON (node.standard);
