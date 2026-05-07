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
const SCREENSHOT_PATH =
  process.env.E2E_SCREENSHOT_PATH ||
  `${process.env.TEMP || "/tmp"}/tutoring_composer_e2e.png`;

async function bodyText(page) {
  return page.locator("body").innerText().catch(() => "");
}

async function waitUntil(page, predicate, timeout = 30000, step = 600) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const currentText = await bodyText(page);
    if (predicate(currentText)) return currentText;
    await page.waitForTimeout(step);
  }
  return bodyText(page);
}

async function clickVisibleButtonContaining(page, text) {
  const target = await page.locator("button").evaluateAll((buttons, label) => {
    const button = buttons.find((item) => {
      const rect = item.getBoundingClientRect();
      return item.innerText.includes(label) && rect.width > 0 && rect.height > 0;
    });
    if (!button) return null;

    const rect = button.getBoundingClientRect();
    return {
      x: rect.x + rect.width / 2,
      y: rect.y + rect.height / 2,
      text: button.innerText,
    };
  }, text);

  if (!target) return false;
  await page.mouse.click(target.x, target.y);
  return true;
}

async function clickQuestionButton(page, questionNumber) {
  const target = await page.locator("button").evaluateAll((buttons, number) => {
    const button = buttons.find((item) => {
      const label = item.innerText.trim();
      const rect = item.getBoundingClientRect();
      return (
        (label === String(number) || label.startsWith(`${number} `)) &&
        rect.width > 0 &&
        rect.height > 0
      );
    });
    if (!button) return null;

    const rect = button.getBoundingClientRect();
    return {
      x: rect.x + rect.width / 2,
      y: rect.y + rect.height / 2,
      text: button.innerText,
    };
  }, questionNumber);

  if (!target) throw new Error(`Question button ${questionNumber} was not found.`);
  await page.mouse.click(target.x, target.y);
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

  await page.locator('input[aria-label="账号/学号"]').first().fill(USERNAME);
  await page.locator('input[aria-label="密码"]').first().fill(PASSWORD);
  await page.getByRole("button", { name: "进入系统" }).click();
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
        text.includes(`进度： ${questionNumber} / 10`) ||
        text.includes(`第 ${questionNumber} 题`),
      20000
    );

    const answerInput = page.locator("textarea").first();
    if ((await answerInput.count()) > 0) {
      await answerInput.click();
      await answerInput.fill("");
      await page.keyboard.type(ANSWER_TEXT, { delay: 30 });
      await page.keyboard.press("Tab");
      await page.waitForTimeout(900);
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

  const target = await page.locator("button").evaluateAll((buttons) => {
    const button =
      buttons.find((item) => item.innerText.includes("❌ 错误")) ||
      buttons.find((item) => item.innerText.includes("✅ 正确"));
    if (!button) return null;

    const rect = button.getBoundingClientRect();
    return {
      x: rect.x + rect.width / 2,
      y: rect.y + rect.height / 2,
      text: button.innerText,
    };
  });

  if (!target) throw new Error("No review question button was found.");
  await page.mouse.click(target.x, target.y);
  await waitUntil(
    page,
    (text) => text.includes("请在下方输入智能辅导提示词"),
    30000
  );
}

async function exerciseComposer(page) {
  await page
    .getByText("👇🏻请在下方输入智能辅导提示词")
    .scrollIntoViewIfNeeded()
    .catch(() => {});
  await page.waitForTimeout(2500);

  const emptySendClicked = await clickVisibleButtonContaining(page, "发送");
  if (!emptySendClicked) throw new Error("Send button was not found.");
  await waitUntil(page, (text) => text.includes("请输入辅导问题后再发送"), 15000);

  const componentFrame = page.frames().find((frame) =>
    frame.url().includes("/component/math_comp")
  );
  if (!componentFrame) throw new Error("Math composer iframe was not found.");

  const editor = componentFrame.locator(".mixed-editor");
  await editor.click();
  await page.keyboard.type("请帮我检查这一步 123", { delay: 20 });
  await page.keyboard.press("Enter");
  await page.keyboard.type("我想先看思路", { delay: 20 });

  await componentFrame.getByRole("button", { name: /插入公式框/ }).click();
  await page.waitForTimeout(700);
  const mathField = componentFrame.locator("math-field").last();
  await mathField.click();
  await page.keyboard.type("x+1", { delay: 20 });
  await page.waitForTimeout(800);

  const selects = componentFrame.locator("select");
  if ((await selects.count()) >= 2) {
    await selects.nth(0).selectOption("2");
    await selects.nth(1).selectOption("2");
  }
  const matrixButton = componentFrame.getByRole("button", { name: /插入矩阵/ }).first();
  if ((await matrixButton.count()) > 0) await matrixButton.click();
  await page.waitForTimeout(1000);

  const finalText = await editor.evaluate((element) => element.textContent);
  const latexValues = await componentFrame
    .locator("math-field")
    .evaluateAll((fields) =>
      fields.map((field) =>
        field.getValue ? field.getValue("latex-without-placeholders") : field.value
      )
    );

  if (!finalText.includes("请帮我检查这一步")) {
    throw new Error(`Composer text was not retained: ${finalText}`);
  }
  if (!latexValues.some((value) => value.includes("x+1"))) {
    throw new Error(`Formula latex was not retained: ${JSON.stringify(latexValues)}`);
  }

  if (RUN_REAL_SEND) {
    const sent = await clickVisibleButtonContaining(page, "发送");
    if (!sent) throw new Error("Send button was not available after input.");
    await waitUntil(
      page,
      (text) => text.includes("正在生成智能辅导") || text.includes("泄露检测"),
      30000
    );
  }

  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true });
  return { finalText, latexValues, screenshot: SCREENSHOT_PATH };
}

(async () => {
  const browser = await chromium.launch({ headless: true, channel: "chrome" });
  const page = await browser.newPage({ viewport: { width: 1365, height: 1500 } });

  try {
    await loginIfNeeded(page);
    await enterCourseIfNeeded(page);
    await completeQuizIfNeeded(page);
    await selectReviewQuestion(page);
    const result = await exerciseComposer(page);
    console.log(JSON.stringify(result, null, 2));
  } finally {
    await browser.close();
  }
})();
