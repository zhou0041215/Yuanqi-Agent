import { describe, expect, it } from 'vitest';

import {
  approvalActionLabel,
  approvalParameterLabels,
  formatApprovalParameter,
  visibleApprovalParameters,
} from './approvalPresentation';

describe('approval presentation', () => {
  it('uses readable labels for Agent write tools and parameters', () => {
    expect(approvalActionLabel('create_patient', 'Medical operation.')).toBe('创建患者');
    expect(approvalActionLabel('create_prescription', 'Medical operation.')).toBe('创建处方');
    expect(approvalParameterLabels.doctor_name).toBe('医生');
    expect(approvalParameterLabels.drugs).toBe('药品信息');
  });

  it('shows missing values clearly and translates gender', () => {
    expect(formatApprovalParameter('birth_date', null)).toBe('未提供');
    expect(formatApprovalParameter('gender', 'UNKNOWN')).toBe('未知');
    expect(formatApprovalParameter('total_amount', 1)).toBe('1 元');
  });

  it('masks phone and identity numbers', () => {
    expect(formatApprovalParameter('phone', '13800138000')).toBe('138****8000');
    expect(formatApprovalParameter('id_card', '110101199001011234')).toBe(
      '110***********1234',
    );
  });

  it('shows the verified patient summary without exposing an editable ID field', () => {
    expect(visibleApprovalParameters({
      patient_id: 7,
      diagnosis: '高血压',
    })).toEqual([['diagnosis', '高血压']]);
  });
});
