import {
  AuditOutlined,
  DeleteOutlined,
  EditOutlined,
  FileAddOutlined,
  MedicineBoxOutlined,
  PlusOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  SendOutlined,
  UserOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Pagination,
  Popconfirm,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  message,
} from 'antd';
import { useCallback, useEffect, useState } from 'react';

import { normalizeAccessToken } from '../api/auth';

interface Envelope<T> { data: T; message: string }
interface PageData<T> {
  content: T[];
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
}
interface Patient {
  id: number;
  patientNo: string;
  name: string;
  gender: string;
  birthDate?: string;
  phone?: string;
  bloodType?: string;
  allergyHistory?: string;
  medicalHistory?: string;
  status: string;
  ownerId: number;
  departmentId: number;
}
interface MedicalRecord {
  id: number;
  recordNo: string;
  visitDate: string;
  department: string;
  doctorName: string;
  diagnosis?: string;
  treatmentPlan?: string;
  status: string;
}
interface Prescription {
  id: number;
  prescriptionNo: string;
  prescriptionDate: string;
  doctorName: string;
  diagnosis?: string;
  drugsJson?: string;
  totalAmount: number;
  status: string;
}
interface PatientWorkspace {
  patient: Patient;
  medicalRecords: MedicalRecord[];
  prescriptions: Prescription[];
}
interface WorkflowApprover {
  userId: number;
  displayName: string;
  departmentName: string;
  roleCode: string;
}
interface WorkflowRequest {
  processInstanceId: string;
  prescriptionId: number;
  targetStatus: 'DISPENSED' | 'CANCELLED';
  approverId: number;
  reason: string;
  createdAt: string;
}
interface ApprovalDraft {
  prescription: Prescription;
  targetStatus: 'DISPENSED' | 'CANCELLED';
}

type CreateKind = 'patient' | 'record' | 'prescription';
const workflowBase = '/api/v1/workflows/prescription-status-changes';

export function ClinicalWorkspace({ accessToken }: { accessToken: string }) {
  const [patients, setPatients] = useState<PageData<Patient> | null>(null);
  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [workspace, setWorkspace] = useState<PatientWorkspace | null>(null);
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [createKind, setCreateKind] = useState<CreateKind | null>(null);
  const [editingPatientId, setEditingPatientId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [approvalDraft, setApprovalDraft] = useState<ApprovalDraft | null>(null);
  const [approvers, setApprovers] = useState<WorkflowApprover[]>([]);
  const [activeRequests, setActiveRequests] = useState<WorkflowRequest[]>([]);
  const [approversLoading, setApproversLoading] = useState(false);
  const [form] = Form.useForm();
  const [approvalForm] = Form.useForm();

  const request = useCallback(async <T,>(
    path: string,
    init?: RequestInit,
  ): Promise<T> => {
    const response = await fetch(path, {
      ...init,
      headers: {
        Authorization: `Bearer ${normalizeAccessToken(accessToken)}`,
        'Content-Type': 'application/json',
        ...(init?.headers ?? {}),
      },
    });
    if (!response.ok) throw new Error(await readError(response));
    if (response.status === 204) return undefined as T;
    const payload = await response.json() as Envelope<T>;
    return payload.data;
  }, [accessToken]);

  const loadPatients = useCallback(async (targetPage = page) => {
    setLoading(true);
    setError('');
    try {
      const query = new URLSearchParams({ page: String(targetPage), size: '12' });
      if (keyword.trim()) query.set('keyword', keyword.trim());
      setPatients(await request<PageData<Patient>>(`/api/v1/patients?${query}`));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '患者列表加载失败');
    } finally {
      setLoading(false);
    }
  }, [keyword, page, request]);

  useEffect(() => { void loadPatients(); }, [loadPatients]);

  const openWorkspace = async (patient: Patient) => {
    setWorkspaceLoading(true);
    setWorkspace({ patient, medicalRecords: [], prescriptions: [] });
    try {
      const [nextWorkspace, requests] = await Promise.all([
        request<PatientWorkspace>(`/api/v1/patients/${patient.id}/workspace`),
        request<WorkflowRequest[]>(`${workflowBase}/requests/my`),
      ]);
      setWorkspace(nextWorkspace);
      setActiveRequests(requests);
    } catch (cause) {
      message.error(cause instanceof Error ? cause.message : '患者工作区加载失败');
    } finally {
      setWorkspaceLoading(false);
    }
  };

  const openApproval = async (
    prescription: Prescription,
    targetStatus: ApprovalDraft['targetStatus'],
  ) => {
    approvalForm.resetFields();
    approvalForm.setFieldsValue({
      reason: targetStatus === 'DISPENSED'
        ? '处方已完成复核，申请发药'
        : '临床计划调整，申请取消处方',
    });
    setApprovalDraft({ prescription, targetStatus });
    setApprovers([]);
    setApproversLoading(true);
    try {
      const candidates = await request<WorkflowApprover[]>(
        `${workflowBase}/approvers?prescriptionId=${prescription.id}`,
      );
      setApprovers(candidates);
      if (candidates.length === 1) approvalForm.setFieldValue('approverId', candidates[0]?.userId);
    } catch (cause) {
      message.error(cause instanceof Error ? cause.message : '审批人加载失败');
    } finally {
      setApproversLoading(false);
    }
  };

  const submitApproval = async () => {
    if (!approvalDraft) return;
    const values = await approvalForm.validateFields();
    setSubmitting(true);
    try {
      const created = await request<{ processInstanceId: string }>(workflowBase, {
        method: 'POST',
        headers: { 'Idempotency-Key': `prescription-workflow-${crypto.randomUUID()}` },
        body: JSON.stringify({
          prescriptionId: approvalDraft.prescription.id,
          targetStatus: approvalDraft.targetStatus,
          approverId: values.approverId,
          reason: values.reason.trim(),
        }),
      });
      message.success(
        `${approvalDraft.targetStatus === 'DISPENSED' ? '发药' : '取消'}申请已提交，流程 ${created.processInstanceId}`,
      );
      setApprovalDraft(null);
      approvalForm.resetFields();
      setActiveRequests(await request<WorkflowRequest[]>(`${workflowBase}/requests/my`));
    } catch (cause) {
      message.error(cause instanceof Error ? cause.message : '审批申请提交失败');
    } finally {
      setSubmitting(false);
    }
  };

  const openCreate = (kind: CreateKind) => {
    setEditingPatientId(null);
    form.resetFields();
    const stamp = Date.now();
    if (kind === 'patient') {
      form.setFieldsValue({
        patientNo: `P-${stamp}`,
        gender: 'UNKNOWN',
        status: 'ACTIVE',
        ownerId: 1001,
        departmentId: 10,
      });
    } else if (kind === 'record') {
      form.setFieldsValue({
        recordNo: `MR-${stamp}`,
        patientId: workspace?.patient.id,
        visitDate: new Date().toISOString().slice(0, 19),
        status: 'ACTIVE',
        ownerId: workspace?.patient.ownerId,
        departmentId: workspace?.patient.departmentId,
      });
    } else {
      form.setFieldsValue({
        prescriptionNo: `RX-${stamp}`,
        patientId: workspace?.patient.id,
        prescriptionDate: new Date().toISOString().slice(0, 19),
        drugsJson: '[]',
        totalAmount: 1,
        status: 'PENDING',
        ownerId: workspace?.patient.ownerId,
        departmentId: workspace?.patient.departmentId,
      });
    }
    setCreateKind(kind);
  };

  const openPatientEdit = (patient: Patient) => {
    setEditingPatientId(patient.id);
    setCreateKind('patient');
    form.setFieldsValue(patient);
  };

  const submitCreate = async () => {
    const values = await form.validateFields();
    setSubmitting(true);
    try {
      const path = createKind === 'patient'
        ? editingPatientId ? `/api/v1/patients/${editingPatientId}` : '/api/v1/patients'
        : createKind === 'record'
          ? '/api/v1/medical-records'
          : '/api/v1/prescriptions';
      await request(path, {
        method: editingPatientId ? 'PATCH' : 'POST',
        headers: { 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify(values),
      });
      message.success(editingPatientId ? '患者资料已更新' : createKind === 'patient' ? '患者已创建' : createKind === 'record' ? '病历已创建' : '处方已创建');
      setCreateKind(null);
      setEditingPatientId(null);
      if (workspace && editingPatientId === workspace.patient.id) await openWorkspace({ ...workspace.patient, ...values });
      if (workspace && createKind !== 'patient') await openWorkspace(workspace.patient);
      await loadPatients();
    } catch (cause) {
      message.error(cause instanceof Error ? cause.message : '创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  const deletePatient = async (patient: Patient) => {
    try {
      await request<void>(`/api/v1/patients/${patient.id}`, {
        method: 'DELETE',
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      });
      message.success('患者已停用');
      if (workspace?.patient.id === patient.id) setWorkspace(null);
      await loadPatients();
    } catch (cause) {
      message.error(cause instanceof Error ? cause.message : '停用失败');
    }
  };

  const deactivateChild = async (kind: 'medical-records' | 'prescriptions', id: number) => {
    try {
      await request<void>(`/api/v1/${kind}/${id}`, {
        method: 'DELETE',
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      });
      message.success(kind === 'medical-records' ? '病历已停用' : '处方已停用');
      if (workspace) await openWorkspace(workspace.patient);
    } catch (cause) {
      message.error(cause instanceof Error ? cause.message : '停用失败');
    }
  };

  return (
    <div className="clinical-page">
      <section className="clinical-hero">
        <div>
          <span>受保护的患者业务区</span>
          <h2>患者健康工作台</h2>
          <p>当前页面包含患者隐私信息，所有读取和修改均通过业务服务重新校验权限。</p>
          <div className="clinical-boundary-strip" aria-label="患者数据安全状态">
            <strong><SafetyCertificateOutlined /> 身份已验证</strong>
            <strong><TeamOutlined /> 按科室与负责人授权</strong>
            <strong><AuditOutlined /> 敏感操作留痕</strong>
          </div>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => void loadPatients()}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => openCreate('patient')}>新建患者</Button>
        </Space>
      </section>

      <Card className="clinical-search-card">
        <Input.Search
          allowClear
          value={keyword}
          prefix={<SearchOutlined />}
          placeholder="按患者姓名、编号或手机号搜索"
          enterButton="查询"
          onChange={(event) => setKeyword(event.target.value)}
          onSearch={() => { setPage(0); void loadPatients(0); }}
        />
      </Card>

      {error && <Alert type="error" showIcon title="无法加载患者数据" description={error} />}
      <Spin spinning={loading}>
        <div className="clinical-grid">
          {patients?.content.map((patient) => (
            <Card key={patient.id} className="patient-card" hoverable onClick={() => void openWorkspace(patient)}>
              <div className="patient-card-heading">
                <span className="patient-avatar"><UserOutlined /></span>
                <div><strong>{patient.name}</strong><small>{patient.patientNo}</small></div>
                <Tag color={patient.status === 'ACTIVE' ? 'green' : 'default'}>{patient.status}</Tag>
              </div>
              <Descriptions size="small" column={2} colon={false}>
                <Descriptions.Item label="性别">{patient.gender}</Descriptions.Item>
                <Descriptions.Item label="血型">{patient.bloodType || '—'}</Descriptions.Item>
                <Descriptions.Item label="科室">{patient.departmentId}</Descriptions.Item>
                <Descriptions.Item label="负责人">{patient.ownerId}</Descriptions.Item>
              </Descriptions>
              <div className="patient-card-actions">
                <Button size="small" onClick={(event) => { event.stopPropagation(); void openWorkspace(patient); }}>查看工作区</Button>
                <Popconfirm
                  title="确认停用该患者？"
                  description="这是软删除操作，历史病历和处方不会丢失。"
                  onConfirm={() => void deletePatient(patient)}
                >
                  <Button size="small" danger icon={<DeleteOutlined />} onClick={(event) => event.stopPropagation()}>停用</Button>
                </Popconfirm>
              </div>
            </Card>
          ))}
        </div>
        {!loading && patients?.content.length === 0 && <Card><Empty description="没有符合条件的患者" /></Card>}
      </Spin>
      <Pagination
        current={(patients?.page ?? 0) + 1}
        pageSize={patients?.size ?? 12}
        total={patients?.totalElements ?? 0}
        showTotal={(total) => `共 ${total} 位患者`}
        onChange={(next) => { setPage(next - 1); }}
      />

      <Drawer
        width={760}
        open={Boolean(workspace)}
        title={workspace ? `${workspace.patient.name} · ${workspace.patient.patientNo}` : '患者工作区'}
        onClose={() => setWorkspace(null)}
        extra={<Space>
          <Button icon={<ReloadOutlined />} onClick={() => workspace && void openWorkspace(workspace.patient)}>刷新</Button>
          <Button icon={<EditOutlined />} onClick={() => workspace && openPatientEdit(workspace.patient)}>编辑患者</Button>
          <Button icon={<FileAddOutlined />} onClick={() => openCreate('record')}>新增病历</Button>
          <Button type="primary" icon={<MedicineBoxOutlined />} onClick={() => openCreate('prescription')}>新增处方</Button>
        </Space>}
      >
        <Spin spinning={workspaceLoading}>
          {workspace && (
            <>
              <Descriptions bordered size="small" column={2}>
                <Descriptions.Item label="患者编号">{workspace.patient.patientNo}</Descriptions.Item>
                <Descriptions.Item label="状态">{workspace.patient.status}</Descriptions.Item>
                <Descriptions.Item label="联系电话">{workspace.patient.phone || '—'}</Descriptions.Item>
                <Descriptions.Item label="过敏史">{workspace.patient.allergyHistory || '无记录'}</Descriptions.Item>
                <Descriptions.Item label="既往史" span={2}>{workspace.patient.medicalHistory || '无记录'}</Descriptions.Item>
              </Descriptions>
              <Tabs
                className="clinical-tabs"
                items={[
                  {
                    key: 'records',
                    label: `病历 ${workspace.medicalRecords.length}`,
                    children: <Table
                      rowKey="id"
                      size="small"
                      pagination={{ pageSize: 8 }}
                      dataSource={workspace.medicalRecords}
                      columns={[
                        { title: '编号', dataIndex: 'recordNo' },
                        { title: '就诊时间', dataIndex: 'visitDate', render: formatDate },
                        { title: '科室', dataIndex: 'department' },
                        { title: '诊断', dataIndex: 'diagnosis', ellipsis: true },
                        { title: '状态', dataIndex: 'status', render: (value) => <Tag>{value}</Tag> },
                        {
                          title: '操作',
                          render: (_, record) => (
                            <Popconfirm title="确认停用该病历？" onConfirm={() => void deactivateChild('medical-records', record.id)}>
                              <Button danger size="small" disabled={record.status !== 'ACTIVE'}>停用</Button>
                            </Popconfirm>
                          ),
                        },
                      ]}
                    />,
                  },
                  {
                    key: 'prescriptions',
                    label: `处方 ${workspace.prescriptions.length}`,
                    children: <Table
                      rowKey="id"
                      size="small"
                      pagination={{ pageSize: 8 }}
                      dataSource={workspace.prescriptions}
                      columns={[
                        { title: '编号', dataIndex: 'prescriptionNo' },
                        { title: '开具时间', dataIndex: 'prescriptionDate', render: formatDate },
                        { title: '医生', dataIndex: 'doctorName' },
                        { title: '金额', dataIndex: 'totalAmount', render: (value) => `¥${Number(value).toFixed(2)}` },
                        { title: '状态', dataIndex: 'status', render: (value) => <Tag color={value === 'PENDING' ? 'gold' : 'blue'}>{value}</Tag> },
                        {
                          title: '操作',
                          render: (_, prescription) => {
                            const activeRequest = activeRequests.find((item) => item.prescriptionId === prescription.id);
                            if (activeRequest) return (
                              <Space wrap>
                                <Tag icon={<SafetyCertificateOutlined />} color="processing">
                                  等待{activeRequest.targetStatus === 'DISPENSED' ? '发药' : '取消'}审批
                                </Tag>
                                <small>审批人 #{activeRequest.approverId}</small>
                              </Space>
                            );
                            return (
                              <Space wrap>
                                <Button
                                  size="small"
                                  type="primary"
                                  icon={<SendOutlined />}
                                  disabled={prescription.status !== 'PENDING'}
                                  onClick={() => void openApproval(prescription, 'DISPENSED')}
                                >
                                  申请发药
                                </Button>
                                <Button
                                  size="small"
                                  disabled={prescription.status !== 'PENDING'}
                                  onClick={() => void openApproval(prescription, 'CANCELLED')}
                                >
                                  申请取消
                                </Button>
                                <Popconfirm
                                  title="确认停用该处方？"
                                  description="停用会隐藏待处理处方；如需正式取消，请走审批流程。"
                                  onConfirm={() => void deactivateChild('prescriptions', prescription.id)}
                                >
                                  <Button danger size="small" disabled={prescription.status !== 'PENDING'}>停用</Button>
                                </Popconfirm>
                              </Space>
                            );
                          },
                        },
                      ]}
                    />,
                  },
                ]}
              />
            </>
          )}
        </Spin>
      </Drawer>

      <Modal
        open={Boolean(approvalDraft)}
        title={approvalDraft?.targetStatus === 'DISPENSED' ? '申请处方发药' : '申请取消处方'}
        okText="提交审批"
        cancelText="取消"
        confirmLoading={submitting}
        okButtonProps={{ disabled: approversLoading || approvers.length === 0 }}
        onCancel={() => { setApprovalDraft(null); approvalForm.resetFields(); }}
        onOk={() => void submitApproval()}
      >
        <Alert
          type="info"
          showIcon
          title="提交后不会立即修改处方"
          description="只有指定审批人同意后，Java 业务层复检权限与处方状态并执行变更。"
        />
        <Descriptions size="small" column={1} style={{ marginBlock: 16 }}>
          <Descriptions.Item label="处方">{approvalDraft?.prescription.prescriptionNo}</Descriptions.Item>
          <Descriptions.Item label="目标状态">
            {approvalDraft?.targetStatus === 'DISPENSED' ? '发药（DISPENSED）' : '取消（CANCELLED）'}
          </Descriptions.Item>
        </Descriptions>
        <Form form={approvalForm} layout="vertical">
          <Form.Item name="approverId" label="审批人" rules={[{ required: true, message: '请选择审批人' }]}>
            <Select
              loading={approversLoading}
              showSearch
              optionFilterProp="label"
              placeholder={approversLoading ? '正在加载有权审批的人员' : '选择另一位有权处理该处方的人员'}
              options={approvers.map((person) => ({
                value: person.userId,
                label: `${person.displayName} · ${person.departmentName}`,
              }))}
              notFoundContent={approversLoading ? '加载中' : '没有其他具备该处方访问权限的审批人'}
            />
          </Form.Item>
          <Form.Item
            name="reason"
            label="申请原因"
            rules={[
              { required: true, whitespace: true, message: '请填写申请原因' },
              { min: 1, max: 1000 },
            ]}
          >
            <Input.TextArea rows={4} maxLength={1000} showCount />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={Boolean(createKind)}
        title={editingPatientId ? '编辑患者资料' : createKind === 'patient' ? '新建患者' : createKind === 'record' ? '新增病历' : '新增处方'}
        width={680}
        okText="提交"
        cancelText="取消"
        confirmLoading={submitting}
        onCancel={() => { setCreateKind(null); setEditingPatientId(null); }}
        onOk={() => void submitCreate()}
      >
        <Form form={form} layout="vertical">
          {createKind === 'patient' && <PatientFields />}
          {createKind === 'record' && <RecordFields />}
          {createKind === 'prescription' && <PrescriptionFields />}
        </Form>
      </Modal>
    </div>
  );
}

function PatientFields() {
  return <>
    <div className="form-grid">
      <Form.Item name="patientNo" label="患者编号" rules={[{ required: true }]}><Input /></Form.Item>
      <Form.Item name="name" label="姓名" rules={[{ required: true }]}><Input /></Form.Item>
      <Form.Item name="gender" label="性别" rules={[{ required: true }]}>
        <Select options={[{ value: 'MALE', label: '男' }, { value: 'FEMALE', label: '女' }, { value: 'UNKNOWN', label: '未知' }]} />
      </Form.Item>
      <Form.Item name="birthDate" label="出生日期"><Input type="date" /></Form.Item>
      <Form.Item name="phone" label="联系电话"><Input /></Form.Item>
      <Form.Item name="bloodType" label="血型"><Input /></Form.Item>
      <Form.Item name="ownerId" label="负责人 ID" rules={[{ required: true }]}><InputNumber min={1} /></Form.Item>
      <Form.Item name="departmentId" label="科室 ID" rules={[{ required: true }]}><InputNumber min={1} /></Form.Item>
    </div>
    <Form.Item name="allergyHistory" label="过敏史"><Input.TextArea rows={2} /></Form.Item>
    <Form.Item name="medicalHistory" label="既往史"><Input.TextArea rows={2} /></Form.Item>
    <Form.Item name="status" hidden><Input /></Form.Item>
  </>;
}

function RecordFields() {
  return <>
    <div className="form-grid">
      <Form.Item name="recordNo" label="病历编号" rules={[{ required: true }]}><Input /></Form.Item>
      <Form.Item name="patientId" label="患者 ID" rules={[{ required: true }]}><InputNumber disabled /></Form.Item>
      <Form.Item name="visitDate" label="就诊时间" rules={[{ required: true }]}><Input type="datetime-local" /></Form.Item>
      <Form.Item name="department" label="就诊科室" rules={[{ required: true }]}><Input /></Form.Item>
      <Form.Item name="doctorName" label="医生" rules={[{ required: true }]}><Input /></Form.Item>
      <Form.Item name="ownerId" label="负责人 ID" rules={[{ required: true }]}><InputNumber min={1} /></Form.Item>
      <Form.Item name="departmentId" label="科室 ID" rules={[{ required: true }]}><InputNumber min={1} /></Form.Item>
    </div>
    <Form.Item name="chiefComplaint" label="主诉"><Input.TextArea rows={2} /></Form.Item>
    <Form.Item name="diagnosis" label="诊断"><Input.TextArea rows={2} /></Form.Item>
    <Form.Item name="treatmentPlan" label="治疗计划"><Input.TextArea rows={2} /></Form.Item>
    <Form.Item name="status" hidden><Input /></Form.Item>
  </>;
}

function PrescriptionFields() {
  return <>
    <div className="form-grid">
      <Form.Item name="prescriptionNo" label="处方编号" rules={[{ required: true }]}><Input /></Form.Item>
      <Form.Item name="patientId" label="患者 ID" rules={[{ required: true }]}><InputNumber disabled /></Form.Item>
      <Form.Item name="prescriptionDate" label="开具时间" rules={[{ required: true }]}><Input type="datetime-local" /></Form.Item>
      <Form.Item name="doctorName" label="医生" rules={[{ required: true }]}><Input /></Form.Item>
      <Form.Item name="totalAmount" label="总金额" rules={[{ required: true }]}><InputNumber min={0.01} precision={2} /></Form.Item>
      <Form.Item name="ownerId" label="负责人 ID" rules={[{ required: true }]}><InputNumber min={1} /></Form.Item>
      <Form.Item name="departmentId" label="科室 ID" rules={[{ required: true }]}><InputNumber min={1} /></Form.Item>
    </div>
    <Form.Item name="diagnosis" label="诊断"><Input.TextArea rows={2} /></Form.Item>
    <Form.Item name="drugsJson" label="药品 JSON" rules={[{ required: true }]}><Input.TextArea rows={4} /></Form.Item>
    <Form.Item name="notes" label="备注"><Input.TextArea rows={2} /></Form.Item>
    <Form.Item name="status" hidden><Input /></Form.Item>
  </>;
}

function formatDate(value: string) {
  return value ? new Date(value).toLocaleString('zh-CN') : '—';
}

async function readError(response: Response) {
  try {
    const payload = await response.json() as { message?: unknown };
    if (typeof payload.message === 'string') return payload.message;
  } catch {
    // Fall through to a status-based error.
  }
  return `请求失败（HTTP ${response.status}）`;
}
