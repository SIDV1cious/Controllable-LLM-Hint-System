const fs = require("node:fs");
const path = require("node:path");

let chromium;

try {
  ({ chromium } = require("playwright"));
} catch (error) {
  console.error(
    [
      "Playwright is required to run this E2E script.",
      "Install it in any Node environment first, for example:",
      "  npm install playwright",
      "",
      `Original error: ${error.message}`,
    ].join("\n")
  );
  process.exit(1);
}

const APP_URL = process.env.E2E_APP_URL || "http://localhost:8517";
const USERNAME = process.env.E2E_STUDENT_USERNAME || "";
const PASSWORD = process.env.E2E_STUDENT_PASSWORD || "";
const COURSE_NAME = process.env.E2E_COURSE_NAME || "高等数学";
const ANSWER_TEXT = process.env.E2E_ANSWER_TEXT || "A";
const RUN_REAL_SEND = process.env.E2E_RUN_REAL_SEND === "1";
const BROWSER_CHANNEL = process.env.E2E_BROWSER_CHANNEL || "chrome";
const SCENARIO_FILTER = (process.env.E2E_SCENARIO_FILTER || "")
  .split(/[,\s]+/)
  .map((item) => item.trim())
  .filter(Boolean);
const SCREENSHOT_PATH =
  process.env.E2E_SCREENSHOT_PATH ||
  `${process.env.TEMP || "/tmp"}/tutoring_composer_e2e.png`;
const REPORT_PATH =
  process.env.E2E_REPORT_PATH ||
  `${process.env.TEMP || "/tmp"}/tutoring_composer_e2e_report.json`;

const SCREENSHOT_DIR = path.dirname(SCREENSHOT_PATH);

function scenarioMatchesFilter(scenario) {
  if (SCENARIO_FILTER.length === 0) return true;
  return SCENARIO_FILTER.some(
    (token) =>
      token === "*" ||
      token === "all" ||
      token === scenario.id ||
      token === scenario.type
  );
}

async function appContext(page) {
  return page.frames().find((frame) => frame.url().includes("/~/+/")) || page;
}

async function bodyText(page) {
  const context = await appContext(page);
  return context.locator("body").innerText().catch(() => "");
}

async function waitUntil(page, predicate, timeout = 30000, step = 600) {
  const start = Date.now();
  let currentText = "";
  while (Date.now() - start < timeout) {
    currentText = await bodyText(page);
    if (predicate(currentText)) return currentText;
    await page.waitForTimeout(step);
  }
  return currentText || (await bodyText(page));
}

async function clickVisibleButtonContaining(page, text) {
  const context = await appContext(page);
  const clicked = await context.locator("button").evaluateAll((buttons, label) => {
    const button = buttons.find((item) => {
      const rect = item.getBoundingClientRect();
      return item.innerText.includes(label) && rect.width > 0 && rect.height > 0;
    });
    if (!button) return false;
    button.click();
    return true;
  }, text);

  await page.waitForTimeout(250);
  return Boolean(clicked);
}

async function clickQuestionButton(page, questionNumber) {
  const context = await appContext(page);
  const clicked = await context.locator("button").evaluateAll((buttons, number) => {
    const button = buttons.find((item) => {
      const label = item.innerText.trim();
      const rect = item.getBoundingClientRect();
      return (
        (label === String(number) || label.startsWith(`${number} `)) &&
        rect.width > 0 &&
        rect.height > 0
      );
    });
    if (!button) return false;
    button.click();
    return true;
  }, questionNumber);

  if (!clicked) throw new Error(`Question button ${questionNumber} was not found.`);
  await page.waitForTimeout(350);
}

async function loginIfNeeded(page) {
  await page.goto(APP_URL, { waitUntil: "domcontentloaded" });
  await waitUntil(
    page,
    (text) => text.includes("进入系统") || text.includes("当前账号"),
    45000
  );

  if (!(await bodyText(page)).includes("进入系统")) return;
  if (!USERNAME || !PASSWORD) {
    throw new Error(
      "Login is required. Set E2E_STUDENT_USERNAME and E2E_STUDENT_PASSWORD."
    );
  }

  const context = await appContext(page);
  await context.locator('input[aria-label="账号/学号"]').first().fill(USERNAME);
  await context.locator('input[aria-label="密码"]').first().fill(PASSWORD);
  await context.getByRole("button", { name: "进入系统" }).click();
  await waitUntil(
    page,
    (text) =>
      text.includes("课程学习大厅") ||
      text.includes("题目列表") ||
      text.includes("作答结果"),
    60000
  );
}

async function enterCourseIfNeeded(page) {
  const currentText = await bodyText(page);
  if (!currentText.includes("课程学习大厅")) return;

  await waitUntil(
    page,
    (text) => text.includes(`进入《${COURSE_NAME}》测验`),
    60000
  );
  const clicked = await clickVisibleButtonContaining(
    page,
    `进入《${COURSE_NAME}》测验`
  );
  if (!clicked) throw new Error(`Course button for ${COURSE_NAME} was not found.`);

  await waitUntil(
    page,
    (text) => text.includes("题目列表") || text.includes("作答结果"),
    60000
  );
}

async function completeQuizIfNeeded(page) {
  if ((await bodyText(page)).includes("作答结果")) return;

  for (let questionNumber = 1; questionNumber <= 10; questionNumber += 1) {
    await clickQuestionButton(page, questionNumber);
    await waitUntil(
      page,
      (text) =>
        text.includes(`进度：${questionNumber} / 10`) ||
        text.includes(`第 ${questionNumber} 题`),
      20000
    );

    const context = await appContext(page);
    const answerInput = context.locator("textarea").first();
    if ((await answerInput.count()) > 0) {
      await answerInput.click();
      await answerInput.fill("");
      await page.keyboard.type(ANSWER_TEXT, { delay: 20 });
      await page.keyboard.press("Tab");
      await page.waitForTimeout(650);
    }
  }

  await clickQuestionButton(page, 10);
  await page.waitForTimeout(1000);
  const submitted = await clickVisibleButtonContaining(page, "提交试卷");
  if (!submitted) throw new Error("Submit button was not found.");

  await waitUntil(
    page,
    (text) => text.includes("作答结果") || text.includes("系统正在阅卷"),
    30000
  );
  await waitUntil(page, (text) => text.includes("作答结果"), 90000);
}

async function selectReviewQuestion(page) {
  if (
    !(await bodyText(page)).includes("请先在左侧选择") &&
    !(await bodyText(page)).includes("等待选择复盘题目")
  ) {
    return;
  }

  const context = await appContext(page);
  const clicked = await context.locator("button").evaluateAll((buttons) => {
    const button =
      buttons.find((item) => item.innerText.includes("错误")) ||
      buttons.find((item) => item.innerText.includes("正确"));
    if (!button) return false;
    button.click();
    return true;
  });

  if (!clicked) throw new Error("No review question button was found.");
  await waitUntil(
    page,
    (text) => text.includes("请在下方输入智能辅导提示词"),
    30000
  );
}

function scenarioScreenshotPath(id) {
  const parsed = path.parse(SCREENSHOT_PATH);
  return path.join(parsed.dir, `${parsed.name}_${id}${parsed.ext || ".png"}`);
}

async function getComponentFrame(page) {
  const deadline = Date.now() + 30000;
  let lastComponentFrame = null;

  while (Date.now() < deadline) {
    const componentFrame = page
      .frames()
      .find((frame) => frame.url().includes("/component/math_comp"));

    if (componentFrame) {
      lastComponentFrame = componentFrame;
      const isReady = await componentFrame
        .locator(".mixed-editor")
        .count()
        .then((count) => count > 0)
        .catch(() => false);

      if (isReady) return componentFrame;
    }

    await page.waitForTimeout(400);
  }

  if (lastComponentFrame) throw new Error("Math composer iframe was found but editor was not ready.");
  throw new Error("Math composer iframe was not found.");
}

async function getEditor(componentFrame) {
  const editor = componentFrame.locator(".mixed-editor");
  if ((await editor.count()) === 0) throw new Error("Composer editor was not found.");
  return editor;
}

async function clearComposer(componentFrame) {
  const editor = await getEditor(componentFrame);
  await editor.evaluate((element) => {
    element.innerHTML = "";
    element.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "deleteContentBackward" }));
  });
  await editor.click();
  await componentFrame.page().waitForTimeout(450);
}

async function readComposerState(componentFrame) {
  const editor = await getEditor(componentFrame);
  const text = await editor.evaluate((element) => element.textContent || "");
  const html = await editor.evaluate((element) => element.innerHTML || "");
  const latexValues = await componentFrame
    .locator("math-field")
    .evaluateAll((fields) =>
      fields.map((field) =>
        field.getValue ? field.getValue("latex-without-placeholders") : field.value
      )
    );
  return { text, html, latexValues };
}

async function forceComposerFlush(page, componentFrame) {
  await componentFrame.locator("body").evaluate((body) => {
    body.dispatchEvent(new MouseEvent("mouseleave", { bubbles: true }));
    body.dispatchEvent(new PointerEvent("pointerleave", { bubbles: true }));
  });
  await page.mouse.move(8, 8);
  await page.waitForTimeout(550);
}

async function insertFormula(componentFrame, latex) {
  await componentFrame.getByRole("button", { name: /插入公式框/ }).click();
  await componentFrame.page().waitForTimeout(500);
  const mathField = componentFrame.locator("math-field").last();
  await mathField.click();
  if (latex) {
    await componentFrame.page().keyboard.type(latex, { delay: 12 });
  }
  await componentFrame.page().waitForTimeout(550);
}

async function openToolbarGroup(componentFrame, name) {
  const group = componentFrame.getByRole("button", { name });
  await group.click();
  await componentFrame.page().waitForTimeout(350);
}

async function setMatrixSize(componentFrame, rows, cols) {
  const selects = componentFrame.locator("select");
  if ((await selects.count()) < 2) {
    throw new Error("Matrix row/column selectors were not found.");
  }
  await selects.nth(0).selectOption(String(rows));
  await selects.nth(1).selectOption(String(cols));
}

async function insertMatrix(componentFrame, rows, cols) {
  await setMatrixSize(componentFrame, rows, cols);
  await componentFrame.getByRole("button", { name: /插入矩阵/ }).click();
  await componentFrame.page().waitForTimeout(700);
}

async function pastePlainText(componentFrame, text) {
  const editor = await getEditor(componentFrame);
  await editor.evaluate((element, value) => {
    const dataTransfer = new DataTransfer();
    dataTransfer.setData("text/plain", value);
    element.dispatchEvent(
      new ClipboardEvent("paste", {
        bubbles: true,
        cancelable: true,
        clipboardData: dataTransfer,
      })
    );
  }, text);
  await componentFrame.page().waitForTimeout(450);
}

function assertIncludes(value, expected, message) {
  if (!String(value).includes(expected)) {
    throw new Error(`${message}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(value)}`);
  }
}

function assertLatexIncludes(values, expected, message) {
  if (!values.some((value) => String(value).includes(expected))) {
    throw new Error(`${message}: expected ${expected}, got ${JSON.stringify(values)}`);
  }
}

async function runScenario(page, scenario, results) {
  const screenshot = scenarioScreenshotPath(scenario.id);
  const startedAt = Date.now();

  try {
    let componentFrame = await getComponentFrame(page);
    await clearComposer(componentFrame);
    componentFrame = await getComponentFrame(page);
    await scenario.run(page, componentFrame);
    await forceComposerFlush(page, componentFrame);
    componentFrame = await getComponentFrame(page);
    const state = await readComposerState(componentFrame);
    await scenario.assert(state, page, componentFrame);
    await page.screenshot({ path: screenshot, fullPage: true });
    results.push({
      scenario_id: scenario.id,
      input_type: scenario.type,
      passed: true,
      actual_text: state.text,
      latex_values: state.latexValues,
      elapsed_ms: Date.now() - startedAt,
      screenshot,
    });
  } catch (error) {
    await page.screenshot({ path: screenshot, fullPage: true }).catch(() => {});
    const state = await getComponentFrame(page)
      .then((frame) => readComposerState(frame))
      .catch(() => ({
        text: "",
        latexValues: [],
      }));
    results.push({
      scenario_id: scenario.id,
      input_type: scenario.type,
      passed: false,
      error: error.message,
      actual_text: state.text,
      latex_values: state.latexValues || [],
      elapsed_ms: Date.now() - startedAt,
      screenshot,
    });
  }
}

const scenarios = [
  {
    id: "empty_send_warning",
    type: "empty-send",
    run: async (page) => {
      const clicked = await clickVisibleButtonContaining(page, "发送");
      if (!clicked) throw new Error("Send button was not found.");
      await waitUntil(page, (text) => text.includes("请输入辅导问题后再发送"), 15000);
    },
    assert: async (_state, page) => {
      assertIncludes(await bodyText(page), "请输入辅导问题后再发送", "Empty warning did not appear");
    },
  },
  {
    id: "plain_chinese_english_emoji",
    type: "plain-text",
    run: async (_page, componentFrame) => {
      const editor = await getEditor(componentFrame);
      await editor.click();
      await componentFrame.page().keyboard.type("你好 ABC 123，标点！🙂", { delay: 15 });
    },
    assert: async (state) => {
      assertIncludes(state.text, "你好 ABC 123", "Plain text was not retained");
      assertIncludes(state.text, "🙂", "Emoji was not retained");
    },
  },
  {
    id: "multiline_and_paste",
    type: "paste-multiline",
    run: async (_page, componentFrame) => {
      const text = "第一行：请提示下一步\n第二行：保留换行与空格  A  B\n第三行：x -> 0";
      await pastePlainText(componentFrame, text);
    },
    assert: async (state) => {
      assertIncludes(state.text, "第一行：请提示下一步", "Pasted first line was not retained");
      assertIncludes(state.text, "第二行：保留换行与空格", "Pasted second line was not retained");
      assertIncludes(state.text, "第三行：x -> 0", "Pasted third line was not retained");
    },
  },
  {
    id: "delete_and_backspace",
    type: "editing",
    run: async (_page, componentFrame) => {
      const editor = await getEditor(componentFrame);
      await editor.click();
      await componentFrame.page().keyboard.type("需要删除X", { delay: 15 });
      await componentFrame.page().keyboard.press("Backspace");
      await componentFrame.page().keyboard.type("，然后继续输入", { delay: 15 });
    },
    assert: async (state) => {
      assertIncludes(state.text, "需要删除，然后继续输入", "Backspace editing was not stable");
    },
  },
  {
    id: "text_formula_text_mix",
    type: "formula-mix",
    run: async (_page, componentFrame) => {
      const editor = await getEditor(componentFrame);
      await editor.click();
      await componentFrame.page().keyboard.type("先看这个公式：", { delay: 15 });
      await insertFormula(componentFrame, "x+1");
      await editor.click();
      await componentFrame.page().keyboard.type("，再判断下一步。", { delay: 15 });
    },
    assert: async (state) => {
      assertIncludes(state.text, "先看这个公式", "Text before formula was not retained");
      assertIncludes(state.text, "再判断下一步", "Text after formula was not retained");
      assertLatexIncludes(state.latexValues, "x+1", "Formula latex was not retained");
    },
  },
  {
    id: "multiple_formulas",
    type: "multiple-formulas",
    run: async (_page, componentFrame) => {
      await insertFormula(componentFrame, "x^2");
      const editor = await getEditor(componentFrame);
      await editor.click();
      await componentFrame.page().keyboard.type(" 和 ", { delay: 15 });
      await insertFormula(componentFrame, "\\sqrt{x}");
    },
    assert: async (state) => {
      assertLatexIncludes(state.latexValues, "x^2", "First formula was not retained");
      assertLatexIncludes(state.latexValues, "\\sqrt{x}", "Second formula was not retained");
    },
  },
  {
    id: "matrix_1x1",
    type: "matrix",
    run: async (_page, componentFrame) => {
      await insertMatrix(componentFrame, 1, 1);
    },
    assert: async (state) => {
      assertLatexIncludes(state.latexValues, "\\begin{pmatrix}", "1x1 matrix was not retained");
    },
  },
  {
    id: "matrix_10x10",
    type: "matrix-large",
    run: async (_page, componentFrame) => {
      await insertMatrix(componentFrame, 10, 10);
    },
    assert: async (state) => {
      assertLatexIncludes(state.latexValues, "\\begin{pmatrix}", "10x10 matrix was not retained");
      const matrixLatex = state.latexValues.find((value) => String(value).includes("\\begin{pmatrix}")) || "";
      if ((matrixLatex.match(/\\\\/g) || []).length < 8) {
        throw new Error(`10x10 matrix appears truncated: ${matrixLatex}`);
      }
    },
  },
  {
    id: "cases_function",
    type: "cases",
    run: async (_page, componentFrame) => {
      await openToolbarGroup(componentFrame, "函数");
      const casesSelect = componentFrame.locator('select[aria-label="插入分段函数"]');
      if ((await casesSelect.count()) === 0) throw new Error("Cases selector was not found.");
      await casesSelect.selectOption("3");
      await componentFrame.page().waitForTimeout(700);
    },
    assert: async (state) => {
      assertLatexIncludes(state.latexValues, "\\begin{cases}", "Cases function was not retained");
    },
  },
  {
    id: "formula_delete",
    type: "formula-delete",
    run: async (_page, componentFrame) => {
      await insertFormula(componentFrame, "x+2");
      const removeButton = componentFrame.locator(".inline-formula-remove").last();
      await removeButton.click();
      await componentFrame.page().waitForTimeout(500);
    },
    assert: async (state) => {
      if (state.latexValues.length !== 0) {
        throw new Error(`Formula was not deleted: ${JSON.stringify(state.latexValues)}`);
      }
    },
  },
  {
    id: "refocus_retention",
    type: "focus",
    run: async (page, componentFrame) => {
      const editor = await getEditor(componentFrame);
      await editor.click();
      await componentFrame.page().keyboard.type("点击外部后仍应保留", { delay: 15 });
      await forceComposerFlush(page, componentFrame);
      await editor.click();
      await componentFrame.page().keyboard.type("，继续输入", { delay: 15 });
    },
    assert: async (state) => {
      assertIncludes(state.text, "点击外部后仍应保留，继续输入", "Refocus text was not retained");
    },
  },
];

function shouldRunRealSendSmoke() {
  if (!RUN_REAL_SEND) return false;
  return scenarioMatchesFilter({ id: "real_send_smoke", type: "send" });
}

async function maybeRunRealSendSmoke(page, componentFrame, results) {
  if (!shouldRunRealSendSmoke()) return;

  const scenario = {
    id: "real_send_smoke",
    type: "send",
    run: async (_page, frame) => {
      const editor = await getEditor(frame);
      await editor.click();
      await frame.page().keyboard.type("请只给我一个方向提示，不要直接说答案。", { delay: 15 });
      await forceComposerFlush(page, frame);
      const sent = await clickVisibleButtonContaining(page, "发送");
      if (!sent) throw new Error("Send button was not available after input.");
      await waitUntil(
        page,
        (text) => text.includes("正在生成智能辅导") || text.includes("泄露检测") || text.includes("受控智能辅导"),
        45000
      );
    },
    assert: async (_state, targetPage) => {
      const text = await bodyText(targetPage);
      if (!text.includes("受控智能辅导") && !text.includes("泄露检测")) {
        throw new Error("Real send smoke did not reach tutoring generation output.");
      }
    },
  };

  await runScenario(page, scenario, results);
}

(async () => {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  const launchOptions = { headless: true };
  if (BROWSER_CHANNEL && BROWSER_CHANNEL !== "chromium") {
    launchOptions.channel = BROWSER_CHANNEL;
  }
  const browser = await chromium.launch(launchOptions);
  const page = await browser.newPage({ viewport: { width: 1365, height: 1500 } });
  const results = [];

  try {
    await loginIfNeeded(page);
    await enterCourseIfNeeded(page);
    await completeQuizIfNeeded(page);
    await selectReviewQuestion(page);

    const selectedScenarios = scenarios.filter(scenarioMatchesFilter);
    if (selectedScenarios.length === 0 && !shouldRunRealSendSmoke()) {
      throw new Error(
        `No E2E scenarios matched E2E_SCENARIO_FILTER=${JSON.stringify(
          SCENARIO_FILTER
        )}.`
      );
    }

    for (const scenario of selectedScenarios) {
      await runScenario(page, scenario, results);
    }
    await maybeRunRealSendSmoke(page, null, results);

    const failed = results.filter((result) => !result.passed);
    const report = {
      app_url: APP_URL,
      run_real_send: RUN_REAL_SEND,
      browser_channel: BROWSER_CHANNEL,
      scenario_filter: SCENARIO_FILTER,
      total: results.length,
      passed: results.length - failed.length,
      failed: failed.length,
      results,
    };

    fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2), "utf8");
    await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true });
    console.log(JSON.stringify(report, null, 2));

    if (failed.length > 0) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
