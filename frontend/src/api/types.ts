export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

export interface ToolCall {
  name: string;
  arguments: Record<string, JsonValue>;
}

export interface AgentPatientContext {
  patientId: number;
  patientNo: string;
  name: string;
}

export interface AgentRunBody {
  threadId?: string;
  mode?: 'knowledge' | 'report';
  message: string;
  history?: Array<{ role: 'user' | 'assistant'; content: string }>;
  toolCall?: ToolCall;
  patientContext?: AgentPatientContext;
}

export interface ChartSeries {
  name?: string;
  type?: 'line' | 'bar' | 'pie' | 'scatter';
  data: Array<number | { name: string; value: number }>;
}

export interface ChartUiData {
  type: 'chart';
  title?: string;
  xAxis?: string[];
  series?: ChartSeries[];
  option?: Record<string, JsonValue>;
}

export interface ApprovalUiData {
  type: 'approval_card';
  threadId: string;
  action: string;
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  tool: string;
  targetParameters: Record<string, JsonValue>;
  fingerprint: string;
}

export type AgentUiData = ChartUiData | ApprovalUiData;

export interface AgentErrorPayload {
  code: string;
  message: string;
  details?: JsonValue;
}

export interface ToolResultPayload {
  toolName: string;
  result: JsonValue;
  formatted: string;
}

export interface ReportFinding {
  item: string;
  result: string;
  reference?: string | null;
  flag: 'high' | 'low' | 'abnormal' | 'unknown';
}

export interface ReportAnalysis {
  fileName: string;
  reportType: string;
  isSynthetic: boolean;
  summary: string;
  findings: ReportFinding[];
  extractedTextPreview: string;
  patientContext: {
    sex?: string | null;
    age?: number | null;
    collectedAt?: string | null;
    reportedAt?: string | null;
    visitReason?: string | null;
    symptoms?: string | null;
    medicalHistory?: string | null;
    currentMedications?: string | null;
    pregnancyStatus?: string | null;
    urgentInstruction?: string | null;
  };
  followUpQuestions: string[];
  warnings: string[];
}

export type AgentStreamEvent =
  | { type: 'reasoning'; reasoning: string }
  | { type: 'text'; text: string }
  | { type: 'uiData'; uiData: AgentUiData }
  | { type: 'tool_result'; toolResult: ToolResultPayload }
  | { type: 'done'; threadId: string; status: string }
  | { type: 'error'; error: AgentErrorPayload };
