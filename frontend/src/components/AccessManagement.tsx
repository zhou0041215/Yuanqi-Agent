import {
  AuditOutlined,
  ClockCircleOutlined,
  EyeOutlined,
  PlusOutlined,
  SafetyCertificateOutlined,
  StopOutlined,
  TeamOutlined,
  UserSwitchOutlined,
} from '@ant-design/icons';
import { Alert, Button, Empty, Input, Modal, Select, Spin, Tag, message } from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';

type View = 'people' | 'patients' | 'roles' | 'grants' | 'audit';
type GrantStatus = 'ACTIVE' | 'EXPIRED' | 'REVOKED';

interface PersonSummary {
  userId: number;
  username: string;
  displayName: string;
  departmentId: number;
  departmentName: string;
  roleCode: string;
  dataScope: string;
  status: string;
}

interface RoleSummary {
  code: string;
  name: string;
  scope: string;
  actions: string[];
}

interface PatientSummary {
  id: number;
  patientNo: string;
  name: string;
  departmentId: number;
  ownerId: number;
  status: string;
}

interface GrantSummary {
  id: number;
  patientId: number;
  patientNo: string;
  patientName: string;
  granteeUserId: number;
  granteeName: string;
  grantedBy: number;
  grantedByName: string;
  reason: string;
  validFrom: string;
  validUntil: string;
  revokedAt: string | null;
  status: GrantStatus;
}

interface AuditSummary {
  occurredAt: string;
  actorUserId: number;
  actorName: string;
  action: string;
  targetLabel: string;
}

interface Snapshot {
  people: PersonSummary[];
  roles: RoleSummary[];
  patients: PatientSummary[];
  grants: GrantSummary[];
  auditEvents: AuditSummary[];
}

interface Props {
  accessToken: string;
}

interface PatientDraft {
  name: string;
  gender: string;
  birthDate: string;
  phone: string;
  bloodType: string;
  allergyHistory: string;
  medicalHistory: string;
  responsibleUserId?: number;
}

interface ClinicalIdentity {
  displayName: string;
  clinicalDepartmentName: string;
}

interface PatientWorkspace {
  patient: PatientSummary & { gender?: string; birthDate?: string; phone?: string; bloodType?: string; allergyHistory?: string; medicalHistory?: string };
  medicalRecords: Array<{ id: number; recordNo: string; visitDate: string; department: string; doctorName: string; diagnosis: string; treatmentPlan: string; status: string }>;
  prescriptions: Array<{ id: number; prescriptionNo: string; prescriptionDate: string; doctorName: string; diagnosis: string; drugsJson: string; status: string }>;
}

const emptyPatientDraft = (): PatientDraft => ({
  name: '',
  gender: '',
  birthDate: '',
  phone: '',
  bloodType: '',
  allergyHistory: '',
  medicalHistory: '',
});

const views: Array<{ key: View; label: string }> = [
  { key: 'people', label: '人员管理' },
  { key: 'patients', label: '患者管理' },
  { key: 'roles', label: '角色与范围' },
  { key: 'grants', label: '患者授权' },
  { key: 'audit', label: '审计日志' },
];

const durationOptions = [
  { value: 4, label: '4 小时' },
  { value: 8, label: '8 小时' },
  { value: 24, label: '24 小时' },
  { value: 72, label: '3 天' },
  { value: 168, label: '7 天' },
  { value: 720, label: '30 天' },
];

const patientStatusLabels: Record<string, string> = {
  ACTIVE: '在诊',
  DISCHARGED: '已出院',
  DECEASED: '已注销',
};

const roleLabels: Record<string, string> = {
  SYSTEM_ADMIN: '系统管理员',
  DEPARTMENT_LEAD: '科室负责人',
  CLINICAL_COLLABORATOR: '临床协作人员',
};

const scopeLabels: Record<string, string> = {
  ALL: '全域数据',
  DEPARTMENT: '本科室',
  SELF: '本人授权',
};

const statusLabels: Record<GrantStatus, string> = {
  ACTIVE: '有效',
  EXPIRED: '已过期',
  REVOKED: '已撤销',
};

async function readResponse(response: Response) {
  const contentType = response.headers.get('content-type') || '';
  const body = contentType.includes('application/json')
    ? await response.json()
    : { message: await response.text() };
  if (!response.ok) throw new Error(body.message || `HTTP ${response.status}`);
  return body;
}

export function AccessManagement({ accessToken }: Props) {
  const [messageApi, messageContextHolder] = message.useMessage();
  const [activeView, setActiveView] = useState<View>('people');
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [patientId, setPatientId] = useState<number>();
  const [granteeUserId, setGranteeUserId] = useState<number>();
  const [durationHours, setDurationHours] = useState(24);
  const [reason, setReason] = useState('');
  const [createConfirmOpen, setCreateConfirmOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<GrantSummary | null>(null);
  const [revoking, setRevoking] = useState(false);
  const [assignmentTarget, setAssignmentTarget] = useState<PatientSummary | null>(null);
  const [nextResponsibleUserId, setNextResponsibleUserId] = useState<number>();
  const [assignmentReason, setAssignmentReason] = useState('');
  const [updatingAssignment, setUpdatingAssignment] = useState(false);
  const [patientCreateOpen, setPatientCreateOpen] = useState(false);
  const [patientDraft, setPatientDraft] = useState<PatientDraft>(emptyPatientDraft);
  const [creatingPatient, setCreatingPatient] = useState(false);
  const [workspacePatient, setWorkspacePatient] = useState<PatientWorkspace | null>(null);
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [clinicalEntry, setClinicalEntry] = useState<'record' | 'prescription' | null>(null);
  const [clinicalSaving, setClinicalSaving] = useState(false);
  const [recordDraft, setRecordDraft] = useState({ visitDate: '', chiefComplaint: '', diagnosis: '', treatmentPlan: '', notes: '' });
  const [prescriptionDraft, setPrescriptionDraft] = useState({ prescriptionDate: '', diagnosis: '', drugsJson: '', totalAmount: '', notes: '' });
  const [clinicalIdentity, setClinicalIdentity] = useState<ClinicalIdentity | null>(null);

  const loadSnapshot = useCallback(async (signal?: AbortSignal, showLoading = false) => {
    if (showLoading) setLoading(true);
    try {
      const response = await fetch('/api/v1/access-management/snapshot', {
        headers: { Authorization: `Bearer ${accessToken}` },
        signal,
      });
      const body = await readResponse(response);
      setSnapshot(body.data);
      setError('');
    } catch (reasonValue) {
      if (!signal?.aborted) {
        setError(reasonValue instanceof Error ? reasonValue.message : '无法加载访问管理数据');
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    const controller = new AbortController();
    void loadSnapshot(controller.signal, true);
    return () => controller.abort();
  }, [loadSnapshot]);

  useEffect(() => {
    const controller = new AbortController();
    void fetch('/api/v1/auth/context', {
      headers: { Authorization: `Bearer ${accessToken}` },
      signal: controller.signal,
    })
      .then(readResponse)
      .then((body) => { if (!controller.signal.aborted) setClinicalIdentity(body.data as ClinicalIdentity); })
      .catch(() => { if (!controller.signal.aborted) setClinicalIdentity(null); });
    return () => controller.abort();
  }, [accessToken]);

  const people = snapshot?.people || [];
  const roles = snapshot?.roles || [];
  const patients = snapshot?.patients || [];
  const grants = snapshot?.grants || [];
  const auditRows = snapshot?.auditEvents || [];
  const eligiblePeople = useMemo(
    () => people.filter((person) => person.status === 'ACTIVE' && person.roleCode !== 'SYSTEM_ADMIN'),
    [people],
  );
  const selectedPatient = patients.find((patient) => patient.id === patientId);
  const selectedPerson = eligiblePeople.find((person) => person.userId === granteeUserId);
  const activeGrantCount = grants.filter((grant) => grant.status === 'ACTIVE').length;
  const expiringSoonCount = grants.filter((grant) => (
    grant.status === 'ACTIVE' && new Date(grant.validUntil).getTime() - Date.now() <= 24 * 60 * 60 * 1000
  )).length;
  const closedGrantCount = grants.filter((grant) => grant.status !== 'ACTIVE').length;
  const canPrepareGrant = Boolean(patientId && granteeUserId && reason.trim().length >= 5);
  const assignedOwner = eligiblePeople.find((person) => person.userId === patientDraft.responsibleUserId);
  const nextResponsiblePerson = eligiblePeople.find((person) => person.userId === nextResponsibleUserId);
  const canCreatePatient = Boolean(
    patientDraft.name.trim()
    && patientDraft.gender
    && patientDraft.responsibleUserId,
  );
  const canUpdateAssignment = Boolean(
    assignmentTarget
    && nextResponsibleUserId
    && nextResponsibleUserId !== assignmentTarget.ownerId
    && assignmentReason.trim().length >= 5,
  );

  const createGrant = async () => {
    if (!patientId || !granteeUserId || !canPrepareGrant) return;
    setCreating(true);
    try {
      const response = await fetch('/api/v1/access-management/grants', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Idempotency-Key': `patient-grant-${crypto.randomUUID()}`,
        },
        body: JSON.stringify({
          patientId,
          granteeUserId,
          reason: reason.trim(),
          validUntil: new Date(Date.now() + durationHours * 60 * 60 * 1000).toISOString(),
        }),
      });
      await readResponse(response);
      setCreateConfirmOpen(false);
      setPatientId(undefined);
      setGranteeUserId(undefined);
      setReason('');
      setDurationHours(24);
      await loadSnapshot();
      messageApi.success('临时授权已创建');
    } catch (reasonValue) {
      messageApi.error(reasonValue instanceof Error ? reasonValue.message : '无法创建临时授权');
    } finally {
      setCreating(false);
    }
  };

  const revokeGrant = async () => {
    if (!revokeTarget) return;
    setRevoking(true);
    try {
      const response = await fetch(`/api/v1/access-management/grants/${revokeTarget.id}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Idempotency-Key': `patient-grant-revoke-${crypto.randomUUID()}`,
        },
      });
      await readResponse(response);
      setRevokeTarget(null);
      await loadSnapshot();
      messageApi.success('患者授权已撤销');
    } catch (reasonValue) {
      messageApi.error(reasonValue instanceof Error ? reasonValue.message : '无法撤销患者授权');
    } finally {
      setRevoking(false);
    }
  };

  const updatePatientAssignment = async () => {
    if (!assignmentTarget || !nextResponsibleUserId || !canUpdateAssignment) return;
    setUpdatingAssignment(true);
    try {
      const response = await fetch(`/api/v1/access-management/patients/${assignmentTarget.id}/assignment`, {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Idempotency-Key': `patient-assignment-${crypto.randomUUID()}`,
        },
        body: JSON.stringify({
          responsibleUserId: nextResponsibleUserId,
          reason: assignmentReason.trim(),
        }),
      });
      await readResponse(response);
      setAssignmentTarget(null);
      setNextResponsibleUserId(undefined);
      setAssignmentReason('');
      await loadSnapshot();
      messageApi.success('患者负责人已移交');
    } catch (reasonValue) {
      messageApi.error(reasonValue instanceof Error ? reasonValue.message : '无法调整患者负责人');
    } finally {
      setUpdatingAssignment(false);
    }
  };

  const createPatient = async () => {
    if (!canCreatePatient || !assignedOwner) return;
    setCreatingPatient(true);
    try {
      const response = await fetch('/api/v1/patients', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Idempotency-Key': `patient-create-${crypto.randomUUID()}`,
        },
        body: JSON.stringify({
          name: patientDraft.name.trim(),
          gender: patientDraft.gender,
          birthDate: patientDraft.birthDate || null,
          phone: patientDraft.phone.trim() || null,
          bloodType: patientDraft.bloodType || null,
          allergyHistory: patientDraft.allergyHistory.trim() || null,
          medicalHistory: patientDraft.medicalHistory.trim() || null,
          responsibleUserId: assignedOwner.userId,
        }),
      });
      await readResponse(response);
      setPatientCreateOpen(false);
      setPatientDraft(emptyPatientDraft());
      await loadSnapshot();
      messageApi.success('患者已添加，可在患者授权中选择');
    } catch (reasonValue) {
      messageApi.error(reasonValue instanceof Error ? reasonValue.message : '无法添加患者');
    } finally {
      setCreatingPatient(false);
    }
  };

  const openPatientWorkspace = async (patientId: number) => {
    setWorkspaceLoading(true);
    try {
      const response = await fetch(`/api/v1/patients/${patientId}/workspace`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      const body = await readResponse(response);
      setWorkspacePatient(body.data);
    } catch (reasonValue) {
      messageApi.error(reasonValue instanceof Error ? reasonValue.message : '无法读取患者详情');
    } finally {
      setWorkspaceLoading(false);
    }
  };

  const refreshWorkspace = async () => {
    if (workspacePatient) await openPatientWorkspace(workspacePatient.patient.id);
  };

  const createClinicalEntry = async () => {
    if (!workspacePatient || !clinicalEntry) return;
    const patient = workspacePatient.patient;
    const isRecord = clinicalEntry === 'record';
    const valid = isRecord
      ? Boolean(recordDraft.visitDate)
      : Boolean(prescriptionDraft.prescriptionDate && prescriptionDraft.drugsJson.trim() && Number(prescriptionDraft.totalAmount) > 0);
    if (!valid) return;
    setClinicalSaving(true);
    try {
      const body = isRecord ? {
        patientId: patient.id, visitDate: recordDraft.visitDate,
        chiefComplaint: recordDraft.chiefComplaint.trim() || null, diagnosis: recordDraft.diagnosis.trim() || null,
        treatmentPlan: recordDraft.treatmentPlan.trim() || null, notes: recordDraft.notes.trim() || null,
      } : {
        patientId: patient.id, recordId: null, prescriptionDate: prescriptionDraft.prescriptionDate,
        diagnosis: prescriptionDraft.diagnosis.trim() || null, drugsJson: prescriptionDraft.drugsJson.trim() || null,
        totalAmount: Number(prescriptionDraft.totalAmount), notes: prescriptionDraft.notes.trim() || null,
      };
      const response = await fetch(isRecord ? '/api/v1/medical-records' : '/api/v1/prescriptions', {
        method: 'POST', headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json', 'Idempotency-Key': `clinical-${clinicalEntry}-${crypto.randomUUID()}` }, body: JSON.stringify(body),
      });
      await readResponse(response);
      setClinicalEntry(null);
      setRecordDraft({ visitDate: '', chiefComplaint: '', diagnosis: '', treatmentPlan: '', notes: '' });
      setPrescriptionDraft({ prescriptionDate: '', diagnosis: '', drugsJson: '', totalAmount: '', notes: '' });
      await refreshWorkspace();
      messageApi.success(isRecord ? '就诊记录已创建' : '处方已创建');
    } catch (reasonValue) {
      messageApi.error(reasonValue instanceof Error ? reasonValue.message : '无法保存临床记录');
    } finally { setClinicalSaving(false); }
  };

  return (
    <section className="access-page" aria-label="人员与数据授权管理">
      {messageContextHolder}
      <header className="access-header">
        <div>
          <span className="access-kicker">ACCESS CONTROL</span>
          <h2>人员与数据授权</h2>
          <p>访问范围随角色、科室与患者授权关系共同生效。</p>
        </div>
        <Tag className="access-readonly" icon={<SafetyCertificateOutlined />}>变更全程留痕</Tag>
      </header>

      <nav className="access-tabs" aria-label="授权管理视图">
        {views.map((view) => (
          <button
            key={view.key}
            className={activeView === view.key ? 'access-tab access-tab--active' : 'access-tab'}
            onClick={() => setActiveView(view.key)}
            aria-pressed={activeView === view.key}
          >
            {view.label}
          </button>
        ))}
      </nav>

      {loading && <div className="access-state"><Spin /><span>正在读取授权边界...</span></div>}
      {error && <Alert className="access-state-error" type="error" showIcon title="无法读取访问管理数据" description={error} />}

      {!loading && !error && activeView === 'people' && (
        <div className="access-content">
          <div className="access-section-heading">
            <div><TeamOutlined /><span>人员目录</span></div>
            <small>{people.length} 名当前工作角色</small>
          </div>
          <div className="access-table-wrap">
            <table className="access-table">
              <thead><tr><th>人员</th><th>所属科室</th><th>工作角色</th><th>数据范围</th><th>状态</th></tr></thead>
              <tbody>{people.map((person) => (
                <tr key={person.userId}>
                  <td><strong>{person.displayName}</strong><span>{person.username}</span></td>
                  <td>{person.departmentName}</td>
                  <td>{roleLabels[person.roleCode] || person.roleCode}</td>
                  <td><Tag>{scopeLabels[person.dataScope] || person.dataScope}</Tag></td>
                  <td><span className="access-status"><i />{person.status === 'ACTIVE' ? '启用' : '停用'}</span></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      )}

      {!loading && !error && activeView === 'patients' && (
        <div className="access-content access-patient-layout">
          <div className="access-patient-intro">
            <div>
              <span className="access-kicker">PATIENT REGISTRY</span>
              <h3>患者归属与协作边界</h3>
              <p>患者必须归属到平台内一位启用的临床人员；科室随负责人自动确定，临时授权只在此基础上扩展读取范围。</p>
            </div>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setPatientCreateOpen(true)}>
              添加患者
            </Button>
          </div>

          <div className="access-patient-rule" role="note">
            <SafetyCertificateOutlined />
            <span>患者归属由负责人和所属科室共同确定。负责人及其数据范围可访问；跨范围协作须经有效临时授权。</span>
          </div>

          <div className="access-section-heading access-patient-list-heading">
            <div><TeamOutlined /><span>患者名册</span></div>
            <small>{patients.length} 位已登记患者</small>
          </div>
          {patients.length === 0 ? (
            <div className="access-grant-empty"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未登记患者" /></div>
          ) : (
            <div className="access-table-wrap">
              <table className="access-table access-table--patients">
                <thead><tr><th>患者</th><th>患者负责人</th><th>诊疗状态</th><th>协作权限</th><th>操作</th></tr></thead>
                <tbody>{patients.map((patient) => {
                  const owner = people.find((person) => person.userId === patient.ownerId);
                  const patientStatus = patient.status || 'ACTIVE';
                  const ownerNeedsTransfer = owner?.roleCode === 'SYSTEM_ADMIN';
                  return (
                    <tr key={patient.id}>
                      <td><strong>{patient.name}</strong><span>{patient.patientNo}</span></td>
                      <td className="access-patient-owner">
                        <strong>{owner?.displayName || '未分配'}</strong>
                        <span>{owner ? `${owner.departmentName} · ${roleLabels[owner.roleCode] || owner.roleCode}` : '请在人员管理中分配负责人'}</span>
                        {ownerNeedsTransfer && <em>系统管理员不能担任患者负责人，请移交</em>}
                      </td>
                      <td><Tag className={`access-patient-status access-patient-status--${patientStatus.toLowerCase()}`}>{patientStatusLabels[patientStatus] || patientStatus}</Tag></td>
                      <td><span className="access-patient-collaboration">跨范围需临时授权</span></td>
                      <td>
                        <Button type="text" size="small" icon={<EyeOutlined />} loading={workspaceLoading} onClick={() => void openPatientWorkspace(patient.id)}>查看详情</Button>
                        <Button
                          type="text"
                          size="small"
                          icon={<UserSwitchOutlined />}
                          onClick={() => {
                            setAssignmentTarget(patient);
                            setNextResponsibleUserId(undefined);
                            setAssignmentReason('');
                          }}
                        >
                          移交负责人
                        </Button>
                      </td>
                    </tr>
                  );
                })}</tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {!loading && !error && activeView === 'roles' && (
        <div className="access-content access-role-list">
          {roles.map((role) => (
            <article className="access-role" key={role.code}>
              <div className="access-role-icon"><UserSwitchOutlined /></div>
              <div className="access-role-main"><h3>{role.name}</h3><p>{role.scope}</p></div>
              <div className="access-role-actions">{role.actions.map((action) => <span key={action}>{action}</span>)}</div>
            </article>
          ))}
        </div>
      )}

      {!loading && !error && activeView === 'grants' && (
        <div className="access-content access-grant-layout">
          <div className="access-grant-stats" aria-label="授权状态概览">
            <div><strong>{activeGrantCount}</strong><span>当前有效</span></div>
            <div><strong>{expiringSoonCount}</strong><span>24 小时内到期</span></div>
            <div><strong>{closedGrantCount}</strong><span>已关闭记录</span></div>
            <p><SafetyCertificateOutlined /> 临时授权仅扩大读取范围，修改权限不会随授权转移。</p>
          </div>

          <section className="access-grant-workbench" aria-labelledby="grant-workbench-title">
            <div className="access-grant-workbench-head">
              <div>
                <span className="access-grant-step">NEW GRANT</span>
                <h3 id="grant-workbench-title">创建临时授权</h3>
              </div>
              <span><ClockCircleOutlined /> 有效期 15 分钟至 30 天</span>
            </div>
            <div className="access-grant-form">
              <label>
                <span>患者</span>
                <Select
                  showSearch
                  optionFilterProp="label"
                  placeholder="选择患者"
                  value={patientId}
                  onChange={setPatientId}
                  options={patients.map((patient) => ({
                    value: patient.id,
                    label: `${patient.name} · ${patient.patientNo}`,
                  }))}
                />
              </label>
              <label>
                <span>授权给</span>
                <Select
                  placeholder="选择协作人员"
                  value={granteeUserId}
                  onChange={setGranteeUserId}
                  options={eligiblePeople.map((person) => ({
                    value: person.userId,
                    label: `${person.displayName} · ${person.departmentName}`,
                  }))}
                />
              </label>
              <label>
                <span>有效期</span>
                <Select value={durationHours} onChange={setDurationHours} options={durationOptions} />
              </label>
              <label className="access-grant-reason">
                <span>授权原因</span>
                <Input.TextArea
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  maxLength={500}
                  autoSize={{ minRows: 2, maxRows: 4 }}
                  placeholder="例如：跨科会诊，需要查看本次就诊相关资料"
                />
              </label>
              <Button
                className="access-grant-create"
                type="primary"
                icon={<PlusOutlined />}
                disabled={!canPrepareGrant}
                onClick={() => setCreateConfirmOpen(true)}
              >
                确认授权信息
              </Button>
            </div>
          </section>

          <div className="access-section-heading access-grant-list-heading">
            <div><AuditOutlined /><span>授权记录</span></div>
            <small>每次读取都会重新校验状态与有效期</small>
          </div>
          {grants.length === 0 ? (
            <div className="access-grant-empty"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无患者授权记录" /></div>
          ) : (
            <div className="access-table-wrap">
              <table className="access-table access-table--grants">
                <thead><tr><th>患者</th><th>授权对象</th><th>授权原因</th><th>有效期至</th><th>状态</th><th>操作</th></tr></thead>
                <tbody>{grants.map((grant) => (
                  <tr key={grant.id}>
                    <td><strong>{grant.patientName}</strong><span>{grant.patientNo}</span></td>
                    <td><strong>{grant.granteeName}</strong><span>由 {grant.grantedByName} 授权</span></td>
                    <td className="access-grant-reason-cell">{grant.reason}</td>
                    <td><time dateTime={grant.validUntil}>{new Date(grant.validUntil).toLocaleString('zh-CN')}</time></td>
                    <td><Tag className={`access-grant-status access-grant-status--${grant.status.toLowerCase()}`}>{statusLabels[grant.status]}</Tag></td>
                    <td>
                      <Button
                        type="text"
                        danger
                        size="small"
                        icon={<StopOutlined />}
                        disabled={grant.status !== 'ACTIVE'}
                        onClick={() => setRevokeTarget(grant)}
                      >
                        撤销
                      </Button>
                    </td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {!loading && !error && activeView === 'audit' && (
        <div className="access-content">
          <div className="access-section-heading"><div><AuditOutlined /><span>访问记录</span></div><small>按时间倒序</small></div>
          <div className="access-table-wrap">
            <table className="access-table access-table--audit">
              <thead><tr><th>时间</th><th>操作人员</th><th>操作</th><th>对象</th></tr></thead>
              <tbody>{auditRows.map((row) => (
                <tr key={`${row.occurredAt}-${row.actorUserId}-${row.action}-${row.targetLabel}`}>
                  <td>{new Date(row.occurredAt).toLocaleString('zh-CN')}</td>
                  <td>{row.actorName}</td><td>{row.action}</td><td>{row.targetLabel}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      )}

      <Modal
        title="确认创建临时授权"
        open={createConfirmOpen}
        okText="创建授权"
        cancelText="返回修改"
        confirmLoading={creating}
        onOk={() => void createGrant()}
        onCancel={() => setCreateConfirmOpen(false)}
      >
        <div className="access-confirm-summary">
          <p><span>患者</span><strong>{selectedPatient?.name} · {selectedPatient?.patientNo}</strong></p>
          <p><span>授权给</span><strong>{selectedPerson?.displayName} · {selectedPerson?.departmentName}</strong></p>
          <p><span>有效期</span><strong>{durationOptions.find((item) => item.value === durationHours)?.label}</strong></p>
          <p><span>原因</span><strong>{reason.trim()}</strong></p>
        </div>
      </Modal>

      <Modal
        title="撤销患者授权"
        open={Boolean(revokeTarget)}
        okText="确认撤销"
        okButtonProps={{ danger: true }}
        cancelText="保留授权"
        confirmLoading={revoking}
        onOk={() => void revokeGrant()}
        onCancel={() => setRevokeTarget(null)}
      >
        <p className="access-revoke-copy">
          撤销后，{revokeTarget?.granteeName} 将立即失去对患者 {revokeTarget?.patientName} 的临时读取权限。
        </p>
      </Modal>

      <Modal
        title="移交患者负责人"
        open={Boolean(assignmentTarget)}
        okText="确认移交"
        cancelText="取消"
        okButtonProps={{ disabled: !canUpdateAssignment }}
        confirmLoading={updatingAssignment}
        onOk={() => void updatePatientAssignment()}
        onCancel={() => {
          if (!updatingAssignment) {
            setAssignmentTarget(null);
            setNextResponsibleUserId(undefined);
            setAssignmentReason('');
          }
        }}
      >
        <div className="access-assignment-form">
          <p>患者 <strong>{assignmentTarget?.name} · {assignmentTarget?.patientNo}</strong> 的长期归属将随负责人同步至其已备案科室。</p>
          <label>
            <span>新负责人</span>
            <Select
              showSearch
              optionFilterProp="label"
              placeholder="选择启用的临床人员"
              value={nextResponsibleUserId}
              options={eligiblePeople
                .filter((person) => person.userId !== assignmentTarget?.ownerId)
                .map((person) => ({
                  value: person.userId,
                  label: `${person.displayName} · ${person.departmentName} · ${roleLabels[person.roleCode] || person.roleCode}`,
                }))}
              onChange={setNextResponsibleUserId}
            />
            {nextResponsiblePerson && <small>移交后归属科室：{nextResponsiblePerson.departmentName}</small>}
          </label>
          <label>
            <span>移交原因</span>
            <Input.TextArea
              autoSize={{ minRows: 2, maxRows: 4 }}
              maxLength={500}
              placeholder="至少 5 个字符，记录负责人调整原因"
              value={assignmentReason}
              onChange={(event) => setAssignmentReason(event.target.value)}
            />
          </label>
        </div>
      </Modal>

      <Modal
        title="添加患者"
        open={patientCreateOpen}
        okText="确认添加患者"
        cancelText="取消"
        okButtonProps={{ disabled: !canCreatePatient }}
        confirmLoading={creatingPatient}
        onOk={() => void createPatient()}
        onCancel={() => {
          if (!creatingPatient) {
            setPatientCreateOpen(false);
            setPatientDraft(emptyPatientDraft());
          }
        }}
        width={720}
      >
        <div className="patient-create-form">
          <p className="patient-create-lead">患者编号会在保存后生成。初始归属按所选人员的已备案科室确定；跨科协作请在“患者授权”中创建有时效的读取授权。</p>
          <label>
            <span>姓名 <b>*</b></span>
            <Input
              value={patientDraft.name}
              maxLength={200}
              placeholder="填写患者姓名"
              onChange={(event) => setPatientDraft((draft) => ({ ...draft, name: event.target.value }))}
            />
          </label>
          <label>
            <span>初始负责人 <b>*</b></span>
            <Select
              placeholder="选择平台内启用人员"
              value={patientDraft.responsibleUserId}
              options={eligiblePeople.map((person) => ({
                value: person.userId,
                label: `${person.displayName} · ${person.departmentName}`,
              }))}
              onChange={(responsibleUserId) => setPatientDraft((draft) => ({ ...draft, responsibleUserId }))}
            />
            {assignedOwner && <small>将归属至：{assignedOwner.departmentName}</small>}
          </label>
          <label>
            <span>性别</span>
            <Select
              allowClear
              placeholder="未填写"
              value={patientDraft.gender || undefined}
              options={[{ value: 'MALE', label: '男' }, { value: 'FEMALE', label: '女' }, { value: 'UNKNOWN', label: '未知' }]}
              onChange={(gender) => setPatientDraft((draft) => ({ ...draft, gender: gender || '' }))}
            />
          </label>
          <label>
            <span>出生日期</span>
            <Input
              type="date"
              value={patientDraft.birthDate}
              onChange={(event) => setPatientDraft((draft) => ({ ...draft, birthDate: event.target.value }))}
            />
          </label>
          <label>
            <span>联系电话</span>
            <Input
              value={patientDraft.phone}
              maxLength={32}
              placeholder="填写联系电话"
              onChange={(event) => setPatientDraft((draft) => ({ ...draft, phone: event.target.value }))}
            />
          </label>
          <label>
            <span>血型</span>
            <Select
              allowClear
              placeholder="未填写"
              value={patientDraft.bloodType || undefined}
              options={['A', 'B', 'AB', 'O', 'RH+','RH-'].map((value) => ({ value, label: value }))}
              onChange={(bloodType) => setPatientDraft((draft) => ({ ...draft, bloodType: bloodType || '' }))}
            />
          </label>
          <label className="patient-create-form__wide">
            <span>过敏史</span>
            <Input.TextArea
              value={patientDraft.allergyHistory}
              maxLength={2000}
              autoSize={{ minRows: 2, maxRows: 3 }}
              placeholder="未填写"
              onChange={(event) => setPatientDraft((draft) => ({ ...draft, allergyHistory: event.target.value }))}
            />
          </label>
          <label className="patient-create-form__wide">
            <span>既往病史</span>
            <Input.TextArea
              value={patientDraft.medicalHistory}
              maxLength={5000}
              autoSize={{ minRows: 2, maxRows: 3 }}
              placeholder="未填写"
              onChange={(event) => setPatientDraft((draft) => ({ ...draft, medicalHistory: event.target.value }))}
            />
          </label>
        </div>
      </Modal>

      <Modal
        title={workspacePatient ? `${workspacePatient.patient.name} · 患者详情` : '患者详情'}
        open={Boolean(workspacePatient)}
        footer={null}
        width={920}
        onCancel={() => setWorkspacePatient(null)}
      >
        {workspacePatient && (
          <div className="patient-workspace">
            <div className="patient-workspace__actions">
              <Button icon={<PlusOutlined />} onClick={() => setClinicalEntry('record')}>新增就诊记录</Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setClinicalEntry('prescription')}>新增处方</Button>
            </div>
            <div className="patient-workspace__summary">
              <div><span>患者编号</span><strong>{workspacePatient.patient.patientNo}</strong></div>
              <div><span>性别 / 出生日期</span><strong>{workspacePatient.patient.gender || '未填写'} / {workspacePatient.patient.birthDate || '未填写'}</strong></div>
              <div><span>联系电话</span><strong>{workspacePatient.patient.phone || '未填写'}</strong></div>
              <div><span>血型</span><strong>{workspacePatient.patient.bloodType || '未填写'}</strong></div>
            </div>
            <div className="patient-workspace__history">
              <section>
                <header><span>就诊记录</span><small>{workspacePatient.medicalRecords.length} 条</small></header>
                {workspacePatient.medicalRecords.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可访问就诊记录" /> : workspacePatient.medicalRecords.map((record) => (
                  <article key={record.id}><strong>{record.diagnosis || '未填写诊断'}</strong><span>{new Date(record.visitDate).toLocaleString('zh-CN')} · {record.department} · {record.doctorName}</span><p>{record.treatmentPlan || '暂无治疗方案'}</p></article>
                ))}
              </section>
              <section>
                <header><span>处方记录</span><small>{workspacePatient.prescriptions.length} 条</small></header>
                {workspacePatient.prescriptions.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可访问处方记录" /> : workspacePatient.prescriptions.map((prescription) => (
                  <article key={prescription.id}><strong>{prescription.diagnosis || '处方记录'}</strong><span>{new Date(prescription.prescriptionDate).toLocaleString('zh-CN')} · {prescription.doctorName}</span><p>{prescription.drugsJson || '未填写药品信息'}</p></article>
                ))}
              </section>
            </div>
            <div className="patient-workspace__note"><strong>过敏史：</strong>{workspacePatient.patient.allergyHistory || '未填写'}<br /><strong>既往病史：</strong>{workspacePatient.patient.medicalHistory || '未填写'}</div>
          </div>
        )}
      </Modal>

      <Modal
        title={clinicalEntry === 'record' ? '新增就诊记录' : '新增处方'}
        open={Boolean(clinicalEntry)}
        okText={clinicalEntry === 'record' ? '确认创建就诊记录' : '确认开具'}
        cancelText="取消"
        confirmLoading={clinicalSaving}
        onOk={() => void createClinicalEntry()}
        onCancel={() => !clinicalSaving && setClinicalEntry(null)}
        width={700}
      >
        {clinicalEntry === 'record' ? (
          <div className="clinical-entry-form">
            <div className="clinical-entry-identity clinical-entry-form__wide">
              <div className="clinical-entry-identity__heading">本次操作</div>
              <div className="clinical-entry-identity__details">
                <div><span>患者</span><strong>{workspacePatient?.patient.name} · {workspacePatient?.patient.patientNo}</strong></div>
                <div><span>接诊医生</span><strong>{clinicalIdentity?.displayName || '正在核验登录身份…'}</strong></div>
                <div><span>就诊科室</span><strong>{clinicalIdentity?.clinicalDepartmentName || '正在核验科室…'}</strong></div>
              </div>
              <small>接诊医生和就诊科室由已验证身份自动写入。</small>
            </div>
            <label><span>就诊时间 *</span><Input type="datetime-local" value={recordDraft.visitDate} onChange={(event) => setRecordDraft((draft) => ({ ...draft, visitDate: event.target.value }))} /></label>
            <label className="clinical-entry-form__wide"><span>主诉</span><Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} value={recordDraft.chiefComplaint} onChange={(event) => setRecordDraft((draft) => ({ ...draft, chiefComplaint: event.target.value }))} /></label>
            <label><span>诊断</span><Input value={recordDraft.diagnosis} onChange={(event) => setRecordDraft((draft) => ({ ...draft, diagnosis: event.target.value }))} /></label>
            <label className="clinical-entry-form__wide"><span>治疗方案</span><Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} value={recordDraft.treatmentPlan} onChange={(event) => setRecordDraft((draft) => ({ ...draft, treatmentPlan: event.target.value }))} /></label>
            <label className="clinical-entry-form__wide"><span>补充说明</span><Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} value={recordDraft.notes} onChange={(event) => setRecordDraft((draft) => ({ ...draft, notes: event.target.value }))} /></label>
          </div>
        ) : (
          <div className="clinical-entry-form">
            <div className="clinical-entry-identity clinical-entry-form__wide">
              <div className="clinical-entry-identity__heading">本次操作</div>
              <div className="clinical-entry-identity__details">
                <div><span>患者</span><strong>{workspacePatient?.patient.name} · {workspacePatient?.patient.patientNo}</strong></div>
                <div><span>开方医生</span><strong>{clinicalIdentity?.displayName || '正在核验登录身份…'}</strong></div>
                <div><span>开方科室</span><strong>{clinicalIdentity?.clinicalDepartmentName || '正在核验科室…'}</strong></div>
              </div>
              <small>开方医生和开方科室由已验证身份自动写入，并计入审计记录。</small>
            </div>
            <label><span>开具时间 *</span><Input type="datetime-local" value={prescriptionDraft.prescriptionDate} onChange={(event) => setPrescriptionDraft((draft) => ({ ...draft, prescriptionDate: event.target.value }))} /></label>
            <label><span>金额 *</span><Input type="number" min="0.01" step="0.01" placeholder="0.00" value={prescriptionDraft.totalAmount} onChange={(event) => setPrescriptionDraft((draft) => ({ ...draft, totalAmount: event.target.value }))} /></label>
            <label><span>诊断</span><Input value={prescriptionDraft.diagnosis} onChange={(event) => setPrescriptionDraft((draft) => ({ ...draft, diagnosis: event.target.value }))} /></label>
            <label className="clinical-entry-form__wide"><span>药品信息</span><Input.TextArea autoSize={{ minRows: 3, maxRows: 6 }} placeholder="填写药品名称、规格、剂量和用法" value={prescriptionDraft.drugsJson} onChange={(event) => setPrescriptionDraft((draft) => ({ ...draft, drugsJson: event.target.value }))} /></label>
            <label className="clinical-entry-form__wide"><span>补充说明</span><Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} value={prescriptionDraft.notes} onChange={(event) => setPrescriptionDraft((draft) => ({ ...draft, notes: event.target.value }))} /></label>
          </div>
        )}
      </Modal>
    </section>
  );
}
