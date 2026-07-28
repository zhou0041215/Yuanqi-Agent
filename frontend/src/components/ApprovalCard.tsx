import {
  CheckOutlined,
  CloseOutlined,
  ExclamationCircleFilled,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { Button, Input, Tag } from 'antd';
import { useState } from 'react';

import type { ApprovalUiData } from '../api/types';

interface Props {
  data: ApprovalUiData;
  disabled: boolean;
  decision?: 'approved' | 'rejected';
  onDecision: (approved: boolean, comment: string) => Promise<void>;
}

const riskLabels = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
  critical: '极高风险',
};

export function ApprovalCard({ data, disabled, decision, onDecision }: Props) {
  const [comment, setComment] = useState('');
  const resolved = decision !== undefined;

  return (
    <section className={`approval-card approval-card--${data.riskLevel}`}>
      <header>
        <div className="approval-symbol">
          <ExclamationCircleFilled />
        </div>
        <div>
          <span className="approval-kicker">需要人工确认</span>
          <h3>{data.action}</h3>
        </div>
        <Tag color={data.riskLevel === 'critical' || data.riskLevel === 'high' ? 'red' : 'orange'}>
          {riskLabels[data.riskLevel]}
        </Tag>
      </header>
      <div className="approval-target">
        <span>目标参数</span>
        <pre>{JSON.stringify(data.targetParameters, null, 2)}</pre>
      </div>
      <div className="approval-proof">
        <SafetyCertificateOutlined /> 指纹 {data.fingerprint.slice(0, 12)}… · {data.tool}
      </div>
      {resolved ? (
        <div className={`decision-stamp decision-stamp--${decision}`}>
          {decision === 'approved' ? '已同意，正在恢复任务' : '已驳回，本次动作不会执行'}
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
              disabled={disabled}
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
