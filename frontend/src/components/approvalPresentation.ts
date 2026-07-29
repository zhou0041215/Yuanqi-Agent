const actionLabels: Record<string, string> = {
  create_patient: '创建患者',
  create_prescription: '创建处方',
  create_medical_record: '创建病历',
};

export const approvalParameterLabels: Record<string, string> = {
  patient_id: '患者系统 ID',
  record_id: '关联病历 ID',
  name: '患者姓名',
  gender: '性别',
  birth_date: '出生日期',
  phone: '联系电话',
  id_card: '身份证号',
  blood_type: '血型',
  allergy_history: '过敏史',
  medical_history: '既往史',
  visit_date: '就诊日期',
  department: '就诊科室',
  doctor_name: '医生',
  chief_complaint: '主诉',
  diagnosis: '诊断',
  treatment_plan: '治疗计划',
  drugs: '药品信息',
  total_amount: '总金额',
  notes: '备注',
};

export function approvalActionLabel(tool: string, fallback: string): string {
  return actionLabels[tool] || fallback;
}

export function visibleApprovalParameters(
  parameters: Record<string, unknown>,
): Array<[string, unknown]> {
  return Object.entries(parameters).filter(
    ([key]) => key !== 'patient_id' && key !== 'patientId',
  );
}

export function formatApprovalParameter(key: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '未提供';
  if (key === 'gender') {
    return { MALE: '男', FEMALE: '女', UNKNOWN: '未知' }[String(value)] || String(value);
  }
  if (key === 'phone') return maskPhone(String(value));
  if (key === 'id_card') return maskIdentityNumber(String(value));
  if (key === 'total_amount' && typeof value === 'number') return `${value} 元`;
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function maskPhone(value: string): string {
  const digits = value.replace(/\D/g, '');
  if (digits.length < 7) return '已提供（已隐藏）';
  return `${digits.slice(0, 3)}****${digits.slice(-4)}`;
}

function maskIdentityNumber(value: string): string {
  const normalized = value.trim();
  if (normalized.length < 8) return '已提供（已隐藏）';
  return `${normalized.slice(0, 3)}***********${normalized.slice(-4)}`;
}
