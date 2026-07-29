import {
  CheckOutlined,
  CloseOutlined,
  ExclamationCircleFilled,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { Button, Input, Tag } from 'antd';
import { useEffect, useMemo, useState } from 'react';

import type { ApprovalUiData } from '../api/types';
import { normalizeAccessToken } from '../api/auth';
import {
  approvalActionLabel,
  approvalParameterLabels,
  formatApprovalParameter,
  visibleApprovalParameters,
} from './approvalPresentation';

interface Props {
  data: ApprovalUiData;
  accessToken: string;
  disabled: boolean;
  decision?: 'approved' | 'rejected';
  status?: string;
  onDecision: (approved: boolean, comment: string) => Promise<void>;
}

interface PatientIdentity {
  id: number;
  patientNo: string;
  name: string;
}

interface PatientEnvelope {
  data?: PatientIdentity;
}

const riskLabels = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
  critical: '极高风险',
};

const configuredBase = window.__YUANQI_CONFIG__?.agentApiBaseUrl ?? import.meta.env.VITE_AGENT_API_BASE_URL;
const apiBase = (configuredBase || '').replace(/\/$/, '');

export function ApprovalCard({ data, accessToken, disabled, decision, status, onDecision }: Props) {
  const [comment, setComment] = useState('');
  const [patient, setPatient] = useState<PatientIdentity | null>(null);
  const [patientState, setPatientState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const resolved = decision !== undefined;
  const patientId = useMemo(() => extractPatientId(data.targetParameters), [data.targetParameters]);
  const action = approvalActionLabel(data.tool, data.action);
  const decisionCompleted = status === 'completed' || status === 'rejected';
  const parameters = visibleApprovalParameters(data.targetParameters);

  useEffect(() => {
    if (patientId === null) {
      setPatient(null);
      setPatientState('idle');
      return;
    }

    const controller = new AbortController();
    setPatient(null);
    setPatientState('loading');
    void fetch(`${apiBase}/api/v1/patients/${patientId}`, {
      headers: {
        Authorization: `Bearer ${normalizeAccessToken(accessToken)}`,
        Accept: 'application/json',
        'X-Trace-Id': crypto.randomUUID(),
      },
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = await response.json() as PatientEnvelope;
        if (!payload.data || payload.data.id !== patientId) {
          throw new Error('患者身份响应无效');
        }
        setPatient(payload.data);
        setPatientState('ready');
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        setPatientState('error');
      });

    return () => controller.abort();
  }, [accessToken, patientId]);

  const identityBlocked = patientId !== null && patientState !== 'ready';

  return (
    <section className={`approval-card approval-card--${data.riskLevel}`}>
      <header>
        <div className="approval-symbol">
          <ExclamationCircleFilled />
        </div>
        <div>
          <span className="approval-kicker">
            {resolved ? '审批已处理' : '需要人工确认'}
          </span>
          <h3>{action}</h3>
        </div>
        <Tag color={data.riskLevel === 'critical' || data.riskLevel === 'high' ? 'red' : 'orange'}>
          {riskLabels[data.riskLevel]}
        </Tag>
      </header>
      {patientId !== null && (
        <div className={`approval-patient approval-patient--${patientState}`}>
          <span>操作对象</span>
          {patientState === 'loading' && <strong>正在核验患者身份…</strong>}
          {patientState === 'ready' && patient && (
            <strong>{patient.name} · {patient.patientNo}</strong>
          )}
          {patientState === 'error' && (
            <strong>无法核验患者身份，已禁止执行。请检查患者权限或重新发起操作。</strong>
          )}
        </div>
      )}
      <div className="approval-target">
        <span>目标参数</span>
        <dl className="approval-parameters">
          {parameters.map(([key, value]) => (
            <div key={key}>
              <dt>{approvalParameterLabels[key] || key}</dt>
              <dd>{formatApprovalParameter(key, value)}</dd>
            </div>
          ))}
        </dl>
      </div>
      <div className="approval-proof">
        <SafetyCertificateOutlined /> 指纹 {data.fingerprint.slice(0, 12)}… · {data.tool}
      </div>
      {resolved ? (
        <div className={`decision-stamp decision-stamp--${decision}`}>
          {decision === 'approved'
            ? decisionCompleted
              ? '已同意并执行，结果见上方'
              : '已同意，正在执行'
            : '已驳回，本次动作不会执行'}
        </div>
      ) : (
        <>
          <Input.TextArea
            value={comment}
            maxLength={500}
            autoSize={{ minRows: 2, maxRows: 4 }}
            placeholder="审批说明（可选）"
            onChange={(event) => setComment(event.target.value)}
          />
          <div className="approval-actions">
            <Button
              danger
              icon={<CloseOutlined />}
              disabled={disabled}
              onClick={() => void onDecision(false, comment)}
            >
              驳回动作
            </Button>
            <Button
              type="primary"
              icon={<CheckOutlined />}
              disabled={disabled || identityBlocked}
              onClick={() => void onDecision(true, comment)}
            >
              同意并执行
            </Button>
          </div>
        </>
      )}
    </section>
  );
}

function extractPatientId(parameters: ApprovalUiData['targetParameters']): number | null {
  const value = parameters.patient_id ?? parameters.patientId;
  return typeof value === 'number' && Number.isInteger(value) && value > 0 ? value : null;
}
