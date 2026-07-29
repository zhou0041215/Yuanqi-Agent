import { describe, expect, it } from 'vitest';

import { attachPatientContext, toAgentPatientContext } from './patientContext';

describe('patient context', () => {
  it('keeps only the patient identity needed by the Agent gateway', () => {
    expect(toAgentPatientContext({
      id: 7,
      patientNo: 'P-0007',
      name: '张三',
    })).toEqual({
      patientId: 7,
      patientNo: 'P-0007',
      name: '张三',
    });
  });

  it('attaches the selected workspace patient to an Agent request', () => {
    const request = attachPatientContext(
      { message: '创建处方' },
      { patientId: 7, patientNo: 'P-0007', name: '张三' },
    );

    expect(request.patientContext).toEqual({
      patientId: 7,
      patientNo: 'P-0007',
      name: '张三',
    });
  });
});
