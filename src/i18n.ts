export type Language = 'en' | 'vi';

export const DEFAULT_LANGUAGE: Language = 'en';

const copy = {
  en: {
    workspace: 'Analytical workspace', overview: 'Overview', reportChat: 'Report & Chat', eda: 'Data health',
    attachTitle: 'Ask your data anything', attachSubtitle: 'Attach a dataset, then review verified analysis with a data copilot.',
    upload: 'Upload a CSV or XLSX', uploadHint: 'Up to 100 MB / 600,000 rows. Your data stays on the server and is never sent as raw rows to an AI model.',
    dataset: 'Dataset', rows: 'rows', columns: 'columns', profileReady: 'Data profile ready', profilePreparing: 'Preparing detailed data health',
    overviewTitle: 'Executive Hub', overviewSub: 'Validated aggregate analysis from the active dataset.', overviewGenerated: 'Generated executive overview', overviewGuardrail: 'All charts are validated server aggregates.', reportEmptyTitle: 'Your Custom Report canvas is ready', reportEmptySub: 'Add verified findings from the Data Copilot to begin an evidence-backed briefing.',
    reportTitle: 'Custom Report', reportSub: 'Curate verified findings into an evidence-backed briefing.',
    copilot: 'Data Copilot', runScoped: 'Run-scoped', openChat: 'Open Data Copilot', closeChat: 'Close Data Copilot', ask: 'Ask about this dataset…', askHelp: 'Enter sends · Shift+Enter adds a line. I will ask for confirmation when a metric, time field, or business meaning is unclear.',
    starter: 'Suggested starting views', starterSub: 'Based on schema and data quality—not raw rows sent to an AI.', generate: 'Generate', addReport: 'Add to report', remove: 'Remove',
    keyFinding: 'Key finding', evidence: 'Evidence', scope: 'Scope', caveat: 'Caveat', suggestions: 'Suggested analyses',
    healthTitle: 'Data health & EDA', healthSub: 'Coverage, quality, cardinality, and bounded distribution facts. Sensitive values are excluded.',
    analyzing: 'Working with your data', preparing: 'Preparing analysis…', chartPending: 'Preparing starter views from the data profile…',
    selected: 'Selected', userConfirmed: 'User-confirmed for this dataset', language: 'Language', english: 'English', vietnamese: 'Tiếng Việt',
    rowsLabel: 'Rows', columnsLabel: 'Columns', analyzed: 'Analyzed', hidden: 'Sensitive fields hidden',
  },
  vi: {
    workspace: 'Không gian phân tích', overview: 'Tổng quan', reportChat: 'Báo cáo & Chat', eda: 'Sức khỏe dữ liệu',
    attachTitle: 'Hỏi mọi điều về dữ liệu của bạn', attachSubtitle: 'Đính kèm dataset để xem phân tích đã được kiểm chứng cùng data copilot.',
    upload: 'Tải lên CSV hoặc XLSX', uploadHint: 'Tối đa 100 MB / 600.000 dòng. Dữ liệu nằm trên server và không gửi raw rows vào AI.',
    dataset: 'Dataset', rows: 'dòng', columns: 'cột', profileReady: 'Profile dữ liệu sẵn sàng', profilePreparing: 'Đang chuẩn bị data health chi tiết',
    overviewTitle: 'Executive Hub', overviewSub: 'Phân tích aggregate đã xác thực từ dataset đang chọn.', overviewGenerated: 'Tổng quan điều hành đã tạo', overviewGuardrail: 'Mọi chart đều là aggregate đã xác thực trên server.', reportEmptyTitle: 'Canvas Custom Report đã sẵn sàng', reportEmptySub: 'Thêm phát hiện đã xác thực từ Data Copilot để bắt đầu bản briefing có evidence.',
    reportTitle: 'Custom Report', reportSub: 'Chọn lọc phát hiện đã xác thực thành bản briefing có evidence.',
    copilot: 'Data Copilot', runScoped: 'Theo run', openChat: 'Mở Data Copilot', closeChat: 'Đóng Data Copilot', ask: 'Hỏi về dataset này…', askHelp: 'Enter để gửi · Shift+Enter để xuống dòng. Em sẽ hỏi lại khi metric, trường thời gian hoặc business meaning chưa rõ.',
    starter: 'Góc nhìn gợi ý', starterSub: 'Dựa vào schema và data quality — không gửi raw rows vào AI.', generate: 'Tạo', addReport: 'Thêm vào báo cáo', remove: 'Xóa',
    keyFinding: 'Phát hiện chính', evidence: 'Bằng chứng', scope: 'Phạm vi', caveat: 'Lưu ý', suggestions: 'Gợi ý phân tích',
    healthTitle: 'Data health & EDA', healthSub: 'Coverage, quality, cardinality và distribution có giới hạn. Giá trị nhạy cảm được loại trừ.',
    analyzing: 'Đang làm việc với dữ liệu', preparing: 'Đang chuẩn bị phân tích…', chartPending: 'Đang tạo starter views từ profile dữ liệu…',
    selected: 'Đã chọn', userConfirmed: 'Đã xác nhận cho dataset này', language: 'Ngôn ngữ', english: 'English', vietnamese: 'Tiếng Việt',
    rowsLabel: 'Dòng', columnsLabel: 'Cột', analyzed: 'Đã phân tích', hidden: 'Trường nhạy cảm đã ẩn',
  },
} as const;

export type CopyKey = keyof typeof copy.en;
export const text = (language: Language, key: CopyKey) => copy[language][key];

export function initialLanguage(): Language {
  const saved = localStorage.getItem('opendata.locale');
  return saved === 'vi' ? 'vi' : DEFAULT_LANGUAGE;
}

export function displayNumber(value: number, language: Language): string {
  return new Intl.NumberFormat(language === 'vi' ? 'vi-VN' : 'en-US').format(value);
}
