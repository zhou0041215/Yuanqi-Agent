import type { AgentPatientContext, AgentRunBody } from './types';

export function toAgentPatientContext(patient: {
  id: number;
  patientNo: string;
  name: string;
}): AgentPatientContext {
  return {
    patientId: patient.id,
    patientNo: patient.patientNo,
    name: patient.name,
  };
}

export function attachPatientContext(
  body: AgentRunBody,
  patientContext?: AgentPatientContext,
): AgentRunBody {
  return patientContext ? { ...body, patientContext } : body;
}
