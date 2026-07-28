"""Real HTTP smoke test for the Java-authenticated medical Agent gateway."""

from __future__ import annotations

import json
from datetime import datetime
from time import time

import httpx


JAVA = "http://127.0.0.1:8080"


def parse_sse(payload: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for frame in payload.replace("\r\n", "\n").split("\n\n"):
        event = "message"
        data_lines: list[str] = []
        for line in frame.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if data_lines:
            events.append((event, json.loads("\n".join(data_lines))))
    return events


def main() -> None:
    with httpx.Client(base_url=JAVA, timeout=60) as client:
        unauthenticated = client.get("/api/v1/kg/search", params={"q": "糖尿病"})
        assert unauthenticated.status_code == 401

        token_response = client.post(
            "/api/v1/dev/token",
            json={
                "userId": 1001,
                "tenantId": 1,
                "username": "admin",
                "dataScope": "ALL",
                "departmentIds": [10],
                "permissions": [
                    "patient:read",
                    "patient:write",
                    "medical-record:read",
                    "medical-record:write",
                    "prescription:read",
                    "prescription:write",
                    "access:manage",
                    "agent:audit:read",
                ],
            },
        )
        token_response.raise_for_status()
        token = token_response.json()["data"]["accessToken"]
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Trace-Id": "trace-java-gateway-smoke-001",
        }
        stamp = int(time() * 1000)

        patient = client.post(
            "/api/v1/patients",
            headers={**headers, "Idempotency-Key": f"smoke-patient-{stamp}"},
            json={
                "patientNo": f"SMOKE-P-{stamp}",
                "name": "Medical gateway smoke patient",
                "gender": "UNKNOWN",
                "status": "ACTIVE",
                "ownerId": 1001,
                "departmentId": 10,
            },
        )
        patient.raise_for_status()
        patient_id = patient.json()["data"]["id"]

        prescription = client.post(
            "/api/v1/prescriptions",
            headers={**headers, "Idempotency-Key": f"smoke-rx-{stamp}"},
            json={
                "prescriptionNo": f"SMOKE-RX-{stamp}",
                "patientId": patient_id,
                "doctorName": "Smoke Doctor",
                "prescriptionDate": datetime.now().isoformat(timespec="seconds"),
                "diagnosis": "Automated smoke test",
                "drugsJson": "[]",
                "totalAmount": 12.5,
                "status": "PENDING",
                "ownerId": 1001,
                "departmentId": 10,
            },
        )
        prescription.raise_for_status()
        prescription_id = prescription.json()["data"]["id"]

        graph = client.get(
            "/api/v1/kg/graph",
            params={"name": "糖尿病", "depth": 1},
            headers=headers,
        )
        graph.raise_for_status()
        graph_payload = graph.json()
        assert graph_payload["nodes"]
        assert graph_payload["links"]

        answer = client.post(
            "/api/v1/agent/stream",
            json={"message": "糖尿病有哪些症状？"},
            headers=headers,
        )
        answer.raise_for_status()
        answer_events = parse_sse(answer.text)
        assert any(event == "tool_result" for event, _ in answer_events)
        assert any(event == "done" for event, _ in answer_events)

        hybrid = client.post(
            "/api/v1/agent/stream",
            json={
                "message": "混合检索糖尿病、多饮和糖化血红蛋白",
                "toolCall": {
                    "name": "search_knowledge",
                    "arguments": {
                        "query": "糖尿病 多饮 糖化血红蛋白",
                        "topK": 8,
                    },
                },
            },
            headers={**headers, "X-Trace-Id": "trace-java-gateway-rrf-001"},
        )
        hybrid.raise_for_status()
        hybrid_events = parse_sse(hybrid.text)
        hybrid_result = next(
            payload["toolResult"]["result"]
            for event, payload in hybrid_events
            if event == "tool_result"
        )
        fused_item = next(
            (
                item
                for item in hybrid_result["items"]
                if set(item["sources"]) == {"graph", "vector"}
            ),
            None,
        )
        if fused_item is None:
            raise AssertionError(
                json.dumps(
                    {
                        "degradedSources": hybrid_result.get("degradedSources"),
                        "items": [
                            {
                                "documentId": item.get("documentId"),
                                "sources": item.get("sources"),
                            }
                            for item in hybrid_result.get("items", [])
                        ],
                    },
                    ensure_ascii=False,
                )
            )

        analysis = client.post(
            "/api/v1/agent/stream",
            json={
                "message": "分析本月处方趋势",
                "toolCall": {
                    "name": "analyze_prescription_snapshot",
                    "arguments": {
                        "fromDate": datetime.now().strftime("%Y-%m-01"),
                        "toDate": datetime.now().strftime("%Y-%m-%d"),
                        "departmentIds": [10],
                        "maximumRows": 100,
                        "code": (
                            "import pandas as pd\n"
                            "df = pd.DataFrame(input_data)\n"
                            "result = {'rowCount': int(len(df)), "
                            "'totalAmount': float(df['total_amount'].sum()) if len(df) else 0}\n"
                            "chart = {'title': {'text': '处方数量'}, "
                            "'xAxis': {'data': ['本月']}, 'yAxis': {}, "
                            "'series': [{'type': 'bar', 'data': [int(len(df))]}]}"
                        ),
                    },
                },
            },
            headers={**headers, "X-Trace-Id": "trace-java-gateway-analysis-001"},
        )
        analysis.raise_for_status()
        analysis_events = parse_sse(analysis.text)
        analysis_result = next(
            payload["toolResult"]["result"]
            for event, payload in analysis_events
            if event == "tool_result"
        )
        assert analysis_result["result"]["dataset"]["deIdentified"] is True
        assert analysis_result["result"]["dataset"]["rowCount"] >= 1

        approval = client.post(
            "/api/v1/agent/stream",
            json={
                "message": "测试处方审批，不执行写入",
                "toolCall": {
                    "name": "create_prescription",
                    "arguments": {
                        "patientId": 1,
                        "doctorName": "测试医生",
                        "diagnosis": "网关审批测试",
                        "drugs": "[]",
                        "totalAmount": 1,
                    },
                },
            },
            headers={**headers, "X-Trace-Id": "trace-java-gateway-hitl-001"},
        )
        approval.raise_for_status()
        approval_events = parse_sse(approval.text)
        if not any(event == "approval" for event, _ in approval_events):
            raise AssertionError(
                f"approval event missing: status={approval.status_code}, body={approval.text!r}"
            )
        approval_payload = next(
            payload["uiData"]
            for event, payload in approval_events
            if event == "approval"
        )

        rejected = client.post(
            f"/api/v1/agent/threads/{approval_payload['threadId']}/resume/stream",
            json={"approved": False, "comment": "自动冒烟测试拒绝"},
            headers={**headers, "X-Trace-Id": "trace-java-gateway-resume-001"},
        )
        rejected.raise_for_status()
        rejected_events = parse_sse(rejected.text)
        done = next(payload for event, payload in rejected_events if event == "done")
        assert done["status"] == "rejected"

        audits = client.get("/api/v1/agent-audit/events", headers=headers)
        audits.raise_for_status()
        audit_events = audits.json()["data"]
        thread_audits = [
            event for event in audit_events
            if event["threadId"] == approval_payload["threadId"]
        ]
        assert any(event["phase"] == "WAITING_APPROVAL" for event in thread_audits)
        assert any(event["outcome"] == "REJECTED" for event in thread_audits)
        assert all("targetParameters" not in event for event in thread_audits)

        workflow = client.post(
            "/api/v1/workflows/prescription-status-changes",
            headers={**headers, "Idempotency-Key": f"smoke-flow-{stamp}"},
            json={
                "prescriptionId": prescription_id,
                "targetStatus": "DISPENSED",
                "approverId": 1010,
                "reason": "Medical gateway Flowable smoke",
            },
        )
        workflow.raise_for_status()
        workflow_task_id = workflow.json()["data"]["taskId"]
        approver_token = client.post(
            "/api/v1/dev/token",
            json={
                "userId": 1010,
                "tenantId": 1,
                "username": "yu_ming_demo",
                "dataScope": "ALL",
                "departmentIds": [10],
                "permissions": ["prescription:read", "prescription:write"],
            },
        )
        approver_token.raise_for_status()
        approver_headers = {
            "Authorization": f"Bearer {approver_token.json()['data']['accessToken']}",
            "X-Trace-Id": "trace-flowable-prescription-001",
            "Idempotency-Key": f"smoke-flow-decision-{stamp}",
        }
        decision = client.post(
            f"/api/v1/workflows/prescription-status-changes/tasks/{workflow_task_id}/decision",
            headers=approver_headers,
            json={"approved": True, "comment": "Smoke approval"},
        )
        decision.raise_for_status()
        read_back = client.get(
            f"/api/v1/prescriptions/{prescription_id}",
            headers=approver_headers,
        )
        read_back.raise_for_status()
        assert read_back.json()["data"]["status"] == "DISPENSED"

        print(
            json.dumps(
                {
                    "unauthenticatedStatus": unauthenticated.status_code,
                    "graphNodes": len(graph_payload["nodes"]),
                    "graphLinks": len(graph_payload["links"]),
                    "answerEvents": [event for event, _ in answer_events],
                    "fusedDocument": fused_item["documentId"],
                    "fusedSources": fused_item["sources"],
                    "approvalRisk": approval_payload["riskLevel"],
                    "resumeStatus": done["status"],
                    "analysisRows": analysis_result["result"]["dataset"]["rowCount"],
                    "auditEvents": len(thread_audits),
                    "flowableStatus": read_back.json()["data"]["status"],
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
