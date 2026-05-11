const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const inputFiles = [
  ...process.argv.slice(2),
  ...(process.env.E2E_REPORT_FILES || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean),
];

const outputPath =
  process.env.E2E_MERGED_REPORT_PATH ||
  path.join(os.tmpdir(), "tutoring_composer_e2e_merged_report.json");

if (inputFiles.length === 0) {
  console.error(
    "Usage: node scripts/e2e_merge_reports.js report-a.json report-b.json ..."
  );
  process.exit(1);
}

function increment(map, key) {
  const safeKey = key || "unknown";
  map[safeKey] = (map[safeKey] || 0) + 1;
}

const reports = inputFiles.map((file) => {
  const raw = fs.readFileSync(file, "utf8");
  return { file, report: JSON.parse(raw) };
});

const results = reports.flatMap(({ file, report }) =>
  (report.results || []).map((result) => ({
    ...result,
    source_report: file,
    active_student_account: report.active_student_account || null,
  }))
);
const failed = results.filter((result) => !result.passed);
const byFailureClass = {};
const byAccount = {};
const byScenarioCategory = {};

for (const result of results) {
  increment(byFailureClass, result.failure_class || (result.passed ? "passed" : "unknown"));
  increment(byAccount, result.active_student_account?.username || "unknown");
  increment(byScenarioCategory, result.category || "unknown");
}

const mergedReport = {
  mode: "merged_report",
  source_report_count: reports.length,
  source_reports: reports.map(({ file, report }) => ({
    file,
    started_at: report.started_at || null,
    finished_at: report.finished_at || null,
    active_student_account: report.active_student_account || null,
    selected_real_send_count: report.selected_real_send_count || 0,
    total: report.total || 0,
    passed: report.passed || 0,
    failed: report.failed || 0,
  })),
  total: results.length,
  passed: results.length - failed.length,
  failed: failed.length,
  by_failure_class: byFailureClass,
  by_account: byAccount,
  by_scenario_category: byScenarioCategory,
  failures: failed.map((result) => ({
    scenario_id: result.scenario_id,
    failure_class: result.failure_class || "unknown",
    error: result.error || "",
    active_student_account: result.active_student_account?.username || null,
    source_report: result.source_report,
    screenshot: result.screenshot || "",
  })),
  merged_at: new Date().toISOString(),
  results,
};

fs.writeFileSync(outputPath, JSON.stringify(mergedReport, null, 2), "utf8");
console.log(JSON.stringify(mergedReport, null, 2));
