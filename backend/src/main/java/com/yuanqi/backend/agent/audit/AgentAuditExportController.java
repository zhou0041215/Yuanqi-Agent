package com.yuanqi.backend.agent.audit;

import com.lowagie.text.Document;
import com.lowagie.text.Element;
import com.lowagie.text.Font;
import com.lowagie.text.Paragraph;
import com.lowagie.text.Phrase;
import com.lowagie.text.pdf.PdfPCell;
import com.lowagie.text.pdf.PdfPTable;
import com.lowagie.text.pdf.PdfWriter;
import java.io.ByteArrayOutputStream;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.List;
import org.apache.poi.xssf.usermodel.XSSFCellStyle;
import org.apache.poi.xssf.usermodel.XSSFFont;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/agent-audit/reports")
@PreAuthorize("hasAuthority('agent:audit:read')")
public class AgentAuditExportController {
    private static final DateTimeFormatter TIME_FORMAT =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss").withZone(ZoneId.systemDefault());
    private final AgentAuditService service;

    public AgentAuditExportController(AgentAuditService service) {
        this.service = service;
    }

    @GetMapping(value = "/xlsx", produces =
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    public ResponseEntity<byte[]> xlsx(@RequestParam(defaultValue = "100") int limit)
            throws Exception {
        List<AgentAuditResponse> rows = service.recent(bounded(limit));
        try (var workbook = new XSSFWorkbook(); var output = new ByteArrayOutputStream()) {
            var sheet = workbook.createSheet("Agent Audit");
            var header = sheet.createRow(0);
            String[] columns = {"Time", "Actor", "Tool", "Phase", "Outcome", "Risk", "Trace ID"};
            XSSFCellStyle headerStyle = workbook.createCellStyle();
            XSSFFont headerFont = workbook.createFont();
            headerFont.setBold(true);
            headerStyle.setFont(headerFont);
            for (int i = 0; i < columns.length; i++) {
                header.createCell(i).setCellValue(columns[i]);
                header.getCell(i).setCellStyle(headerStyle);
            }
            for (int index = 0; index < rows.size(); index++) {
                AgentAuditResponse item = rows.get(index);
                var row = sheet.createRow(index + 1);
                String[] values = values(item);
                for (int column = 0; column < values.length; column++) {
                    row.createCell(column).setCellValue(values[column]);
                }
            }
            for (int i = 0; i < columns.length; i++) sheet.autoSizeColumn(i);
            workbook.write(output);
            return download(output.toByteArray(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx");
        }
    }

    @GetMapping(value = "/pdf", produces = MediaType.APPLICATION_PDF_VALUE)
    public ResponseEntity<byte[]> pdf(@RequestParam(defaultValue = "100") int limit) {
        List<AgentAuditResponse> rows = service.recent(bounded(limit));
        var output = new ByteArrayOutputStream();
        Document document = new Document();
        PdfWriter.getInstance(document, output);
        document.open();
        Paragraph title = new Paragraph(
                "YuanQi Agent Audit Report", new Font(Font.HELVETICA, 16, Font.BOLD));
        title.setAlignment(Element.ALIGN_CENTER);
        document.add(title);
        document.add(new Paragraph("Generated: " + TIME_FORMAT.format(java.time.Instant.now())));
        document.add(new Paragraph("Records: " + rows.size()));
        document.add(new Paragraph(" "));
        PdfPTable table = new PdfPTable(new float[]{2.2f, 1.4f, 2f, 1.2f, 1.2f, 1f, 2.4f});
        table.setWidthPercentage(100);
        for (String heading : new String[]{
                "Time", "Actor", "Tool", "Phase", "Outcome", "Risk", "Trace ID"}) {
            PdfPCell cell = new PdfPCell(
                    new Phrase(heading, new Font(Font.HELVETICA, 8, Font.BOLD)));
            cell.setHorizontalAlignment(Element.ALIGN_CENTER);
            table.addCell(cell);
        }
        Font body = new Font(Font.HELVETICA, 7);
        for (AgentAuditResponse item : rows) {
            for (String value : values(item)) table.addCell(new Phrase(value, body));
        }
        document.add(table);
        document.close();
        return download(output.toByteArray(), MediaType.APPLICATION_PDF_VALUE, "pdf");
    }

    private String[] values(AgentAuditResponse item) {
        return new String[]{
                TIME_FORMAT.format(item.occurredAt()), safe(item.actorName()), safe(item.toolName()),
                safe(item.phase()), safe(item.outcome()), safe(item.riskLevel()), safe(item.traceId())
        };
    }

    private int bounded(int value) { return Math.max(1, Math.min(value, 100)); }
    private String safe(String value) { return value == null ? "" : value; }

    private ResponseEntity<byte[]> download(byte[] body, String contentType, String extension) {
        String filename = "yuanqi-agent-audit-" + LocalDate.now() + "." + extension;
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION,
                        ContentDisposition.attachment().filename(filename).build().toString())
                .contentType(MediaType.parseMediaType(contentType))
                .body(body);
    }
}
