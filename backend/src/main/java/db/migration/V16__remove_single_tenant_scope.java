package db.migration;

import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.List;
import org.flywaydb.core.api.migration.BaseJavaMigration;
import org.flywaydb.core.api.migration.Context;

/** Retires the hard-coded single-tenant schema after verifying it has no multi-tenant data. */
public class V16__remove_single_tenant_scope extends BaseJavaMigration {
    private static final List<String> TENANT_TABLES = List.of(
            "patient", "medical_record", "prescription", "access_person", "patient_access_grant",
            "access_audit_event", "user_account", "agent_audit_event", "answer_feedback",
            "user_notification", "knowledge_document", "knowledge_index_version", "conversation_session");

    @Override
    public void migrate(Context context) throws Exception {
        Connection connection = context.getConnection();
        assertSingleInstitutionData(connection);
        boolean h2 = connection.getMetaData().getDatabaseProductName().equalsIgnoreCase("H2");

        dropIndex(connection, h2, "patient", "idx_patient_tenant");
        dropColumn(connection, "patient", "tenant_id");
        dropIndex(connection, h2, "medical_record", "idx_record_tenant");
        dropColumn(connection, "medical_record", "tenant_id");
        dropIndex(connection, h2, "prescription", "idx_prescription_tenant");
        dropColumn(connection, "prescription", "tenant_id");

        dropUnique(connection, h2, "access_person", "uk_access_person_tenant_user");
        dropUnique(connection, h2, "access_person", "uk_access_person_tenant_username");
        dropIndex(connection, h2, "access_person", "idx_access_person_tenant");
        dropIndex(connection, h2, "access_person", "idx_access_person_department");
        dropColumn(connection, "access_person", "tenant_id");
        execute(connection, "ALTER TABLE access_person ADD CONSTRAINT uk_access_person_user UNIQUE (user_id)");
        execute(connection, "ALTER TABLE access_person ADD CONSTRAINT uk_access_person_username UNIQUE (username)");
        execute(connection, "CREATE INDEX idx_access_person_department ON access_person (department_id)");

        dropIndex(connection, h2, "patient_access_grant", "idx_patient_grant_lookup");
        dropIndex(connection, h2, "patient_access_grant", "idx_patient_grant_expiry");
        dropColumn(connection, "patient_access_grant", "tenant_id");
        execute(connection, "CREATE INDEX idx_patient_grant_lookup ON patient_access_grant (grantee_user_id, patient_id)");
        execute(connection, "CREATE INDEX idx_patient_grant_expiry ON patient_access_grant (valid_until)");

        dropIndex(connection, h2, "access_audit_event", "idx_access_audit_tenant_time");
        dropColumn(connection, "access_audit_event", "tenant_id");
        execute(connection, "CREATE INDEX idx_access_audit_time ON access_audit_event (occurred_at)");

        dropUnique(connection, h2, "user_account", "uk_user_account_tenant_user");
        dropColumn(connection, "user_account", "tenant_id");
        execute(connection, "ALTER TABLE user_account ADD CONSTRAINT uk_user_account_user UNIQUE (user_id)");

        dropIndex(connection, h2, "agent_audit_event", "idx_agent_audit_tenant_time");
        dropIndex(connection, h2, "agent_audit_event", "idx_agent_audit_thread");
        dropColumn(connection, "agent_audit_event", "tenant_id");
        execute(connection, "CREATE INDEX idx_agent_audit_time ON agent_audit_event (occurred_at)");
        execute(connection, "CREATE INDEX idx_agent_audit_thread ON agent_audit_event (thread_id)");

        dropUnique(connection, h2, "answer_feedback", "uk_feedback_tenant_turn_user");
        dropIndex(connection, h2, "answer_feedback", "idx_feedback_tenant_created");
        dropIndex(connection, h2, "answer_feedback", "idx_feedback_tenant_status");
        dropColumn(connection, "answer_feedback", "tenant_id");
        execute(connection, "ALTER TABLE answer_feedback ADD CONSTRAINT uk_feedback_turn_user UNIQUE (turn_id, user_id)");
        execute(connection, "CREATE INDEX idx_feedback_created ON answer_feedback (created_at)");
        execute(connection, "CREATE INDEX idx_feedback_status ON answer_feedback (status)");

        dropIndex(connection, h2, "user_notification", "idx_notification_recipient");
        dropColumn(connection, "user_notification", "tenant_id");
        execute(connection, "CREATE INDEX idx_notification_recipient ON user_notification (recipient_user_id, read_at, created_at)");

        dropUnique(connection, h2, "knowledge_document", "uk_knowledge_tenant_key");
        dropIndex(connection, h2, "knowledge_document", "idx_knowledge_tenant_status");
        dropColumn(connection, "knowledge_document", "tenant_id");
        execute(connection, "ALTER TABLE knowledge_document ADD CONSTRAINT uk_knowledge_document_key UNIQUE (document_key)");
        execute(connection, "CREATE INDEX idx_knowledge_status ON knowledge_document (status, updated_at)");

        dropUnique(connection, h2, "knowledge_index_version", "uk_index_tenant_version");
        dropColumn(connection, "knowledge_index_version", "tenant_id");
        execute(connection, "ALTER TABLE knowledge_index_version ADD CONSTRAINT uk_index_version_name UNIQUE (version_name)");

        dropIndex(connection, h2, "conversation_session", "idx_conversation_owner");
        dropColumn(connection, "conversation_session", "tenant_id");
        execute(connection, "CREATE INDEX idx_conversation_owner ON conversation_session (owner_user_id, archived, updated_at)");
    }

    private void assertSingleInstitutionData(Connection connection) throws SQLException {
        for (String table : TENANT_TABLES) {
            try (Statement statement = connection.createStatement();
                 ResultSet result = statement.executeQuery("SELECT COUNT(DISTINCT tenant_id) FROM " + table)) {
                if (result.next() && result.getLong(1) > 1) {
                    throw new IllegalStateException(
                            "Cannot remove tenant scope: " + table + " contains data from multiple institutions");
                }
            }
        }
    }

    private void dropIndex(Connection connection, boolean h2, String table, String index) throws SQLException {
        execute(connection, h2 ? "DROP INDEX " + index : "ALTER TABLE " + table + " DROP INDEX " + index);
    }

    private void dropUnique(Connection connection, boolean h2, String table, String constraint) throws SQLException {
        execute(connection, h2 ? "ALTER TABLE " + table + " DROP CONSTRAINT " + constraint
                : "ALTER TABLE " + table + " DROP INDEX " + constraint);
    }

    private void dropColumn(Connection connection, String table, String column) throws SQLException {
        execute(connection, "ALTER TABLE " + table + " DROP COLUMN " + column);
    }

    private void execute(Connection connection, String sql) throws SQLException {
        try (Statement statement = connection.createStatement()) {
            statement.execute(sql);
        }
    }
}
