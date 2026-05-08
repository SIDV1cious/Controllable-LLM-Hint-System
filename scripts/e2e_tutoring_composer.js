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
const REAL_SEND_TIMEOUT_MS = Number(process.env.E2E_REAL_SEND_TIMEOUT_MS || 120000);
const COMPOSER_SYNC_SETTLE_MS = 120;
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
      token === scenario.type ||
      (token === "real_send_smoke" && scenario.id === "real_send_plain_immediate")
  );
}

async function appContext(page) {
  return page.frames().find((frame) => frame.url().includes("/~/+/")) || page;
}

async function bodyText(page) {
  const deadline = Date.now() + 5000;
  while (Date.now() < deadline) {
    try {
      const context = await appContext(page);
      return await context.locator("body").innerText({ timeout: 1000 });
    } catch (_error) {
      await page.waitForTimeout(250);
    }
  }
  return "";
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
  const button = await findVisibleEnabledButtonContaining(page, text);
  if (!button) return false;
  await button.click({ timeout: 10000 });
  await page.waitForTimeout(250);
  return true;
}

async function clickVisibleButtonContainingTimes(page, text, times = 1) {
  const target = await findVisibleEnabledButtonContaining(page, text);
  if (!target) return 0;

  let clickedCount = 0;
  for (let index = 0; index < times; index += 1) {
    if (!(await target.isEnabled().catch(() => false))) break;
    try {
      await target.click({ timeout: 1200 });
      clickedCount += 1;
    } catch (error) {
      if (
        String(error.message || "").includes("not enabled") ||
        String(error.message || "").includes("detached") ||
        String(error.message || "").includes("Timeout")
      ) {
        break;
      }
      throw error;
    }
    await page.waitForTimeout(80);
  }

  await page.waitForTimeout(250);
  return clickedCount;
}

async function findVisibleEnabledButtonContaining(page, text) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const target = await findVisibleEnabledButtonOnce(page, text);
    if (target) return target;

    await scrollAppToBottom(page);
    await page.waitForTimeout(350);
  }

  return null;
}

async function scrollAppToBottom(page) {
  const context = await appContext(page);
  await context.evaluate(() => {
    const scrollToBottom = (element) => {
      if (!element) return;
      element.scrollTop = element.scrollHeight;
      if (typeof element.scrollTo === "function") {
        element.scrollTo(0, element.scrollHeight);
      }
    };

    window.scrollTo(0, document.documentElement.scrollHeight || document.body.scrollHeight);
    scrollToBottom(document.documentElement);
    scrollToBottom(document.body);

    const knownContainers = [
      document.querySelector(".stApp"),
      document.querySelector('[data-testid="stAppViewContainer"]'),
      document.querySelector('[data-testid="stMain"]'),
      document.querySelector("section.main"),
    ];
    knownContainers.forEach(scrollToBottom);

    Array.from(document.querySelectorAll("*"))
      .filter((element) => element.scrollHeight > element.clientHeight + 8)
      .forEach(scrollToBottom);
  });
  await page.mouse.wheel(0, 1600);
  await page.waitForTimeout(100);
}

async function findVisibleEnabledButtonOnce(page, text) {
  const context = await appContext(page);
  const buttons = context.locator("button").filter({ hasText: text });
  const total = await buttons.count();

  for (let index = 0; index < total; index += 1) {
    const button = buttons.nth(index);
    if (!(await button.isVisible().catch(() => false))) continue;
    if (!(await button.isEnabled().catch(() => false))) continue;
    return button;
  }

  if (isSendButtonSearch(text)) {
    return await findSendButtonFallback(context);
  }

  return null;
}

async function describeButtonsContaining(page, text) {
  const context = await appContext(page);
  const buttons = context.locator("button").filter({ hasText: text });
  const total = await buttons.count();
  const summaries = [];

  for (let index = 0; index < total; index += 1) {
    const button = buttons.nth(index);
    summaries.push({
      index,
      text: await button.innerText().catch(() => ""),
      visible: await button.isVisible().catch(() => false),
      enabled: await button.isEnabled().catch(() => false),
      box: await button.boundingBox().catch(() => null),
    });
  }

  if (summaries.length === 0 && isSendButtonSearch(text)) {
    const allButtons = context.locator("button");
    const allTotal = await allButtons.count();
    for (let index = 0; index < allTotal; index += 1) {
      const button = allButtons.nth(index);
      if (!(await button.isVisible().catch(() => false))) continue;
      summaries.push({
        index,
        text: await button.innerText().catch(() => ""),
        visible: true,
        enabled: await button.isEnabled().catch(() => false),
        box: await button.boundingBox().catch(() => null),
      });
    }
  }

  return summaries;
}

async function hasVisibleGenerationButton(page) {
  const context = await appContext(page);
  return await context.locator("button").evaluateAll((buttons) =>
    buttons.some((button) => {
      const text = button.innerText || "";
      const rect = button.getBoundingClientRect();
      const style = window.getComputedStyle(button);
      const isVisible =
        rect.width > 0 &&
        rect.height > 0 &&
        style.visibility !== "hidden" &&
        style.display !== "none";
      const isDisabled =
        button.disabled ||
        button.getAttribute("aria-disabled") === "true" ||
        button.classList.contains("disabled");
      return isVisible && isDisabled && text.includes("生成中");
    })
  );
}

async function waitForFinalSendState(page, options = {}) {
  const timeout = options.finalTimeout || REAL_SEND_TIMEOUT_MS;
  const startedAt = Date.now();
  let currentText = "";

  while (Date.now() - startedAt < timeout) {
    currentText = await bodyText(page);
    const finalState = getReplyStateAfterPrompt(currentText, options.expectedPrompt);
    const finalContentVisible =
      finalState.finalReplyVisible && finalState.leakageStatusVisible;
    const stillGenerating =
      currentText.includes("正在生成智能辅导") ||
      (await hasVisibleGenerationButton(page).catch(() => false));

    if (finalContentVisible && !stillGenerating) return currentText;
    await page.waitForTimeout(700);
  }

  return currentText || (await bodyText(page));
}

function getReplyStateAfterPrompt(text, expectedPrompt) {
  const value = String(text || "");
  const startIndex = expectedPrompt ? value.lastIndexOf(expectedPrompt) : 0;
  if (startIndex < 0) {
    return { finalReplyVisible: false, leakageStatusVisible: false };
  }

  const tail = value.slice(startIndex);
  return {
    finalReplyVisible: tail.includes("受控智能辅导"),
    leakageStatusVisible: tail.includes("答案泄露检测状态"),
  };
}

function isSendButtonSearch(text) {
  const value = String(text || "").toLowerCase();
  return (
    value.includes("send") ||
    value.includes("发送") ||
    value.includes("發送") ||
    value.includes("鍙")
  );
}

function textLooksLikeSendButton(text) {
  const value = String(text || "").trim().toLowerCase();
  return (
    value === "send" ||
    value.includes("发送") ||
    value.includes("發送") ||
    value.includes("鍙戦") ||
    value.includes("鍙")
  );
}

async function findSendButtonFallback(context) {
  const buttons = context.locator("button");
  const total = await buttons.count();
  const candidates = [];

  for (let index = 0; index < total; index += 1) {
    const button = buttons.nth(index);
    const visible = await button.isVisible().catch(() => false);
    const enabled = await button.isEnabled().catch(() => false);
    if (!visible || !enabled) continue;

    const label = await button.innerText().catch(() => "");
    const box = await button.boundingBox().catch(() => null);
    if (!box) continue;

    candidates.push({ button, label, box });
  }

  const semanticMatch = candidates.find((candidate) =>
    textLooksLikeSendButton(candidate.label)
  );
  if (semanticMatch) return semanticMatch.button;

  return null;
}

async function clickQuestionButton(page, questionNumber) {
  const context = await appContext(page);
  const deadline = Date.now() + 12000;

  while (Date.now() < deadline) {
    const clicked = await context.locator("button").evaluateAll((buttons, number) => {
      const button = buttons.find((item) => {
        const label = item.innerText.trim();
        const rect = item.getBoundingClientRect();
        const firstNumber = label.match(/\d+/)?.[0];
        const isQuestionNavigation =
          label === String(number) ||
          label.startsWith(`${number} `) ||
          label.startsWith(`${number}\n`) ||
          (label.startsWith(String(number)) && label.length <= 12) ||
          (firstNumber && Number(firstNumber) === number && label.includes("|"));
        return isQuestionNavigation && rect.width > 0 && rect.height > 0;
      });
      if (!button) return false;
      button.click();
      return true;
    }, questionNumber);

    if (clicked) {
      await page.waitForTimeout(350);
      return;
    }

    await page.waitForTimeout(500);
  }

  const text = await bodyText(page);
  throw new Error(`Question button ${questionNumber} was not found. Page text: ${text.slice(0, 500)}`);
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
  if (!(await bodyText(page)).includes("题目列表")) {
    await enterCourseIfNeeded(page);
    await waitUntil(page, (text) => text.includes("题目列表") || text.includes("作答结果"), 60000);
  }
  if ((await bodyText(page)).includes("作答结果")) return;

  const fillCurrentAnswer = async () => {
    const context = await appContext(page);
    const answerInput = context.locator("textarea").first();
    await answerInput.waitFor({ state: "visible", timeout: 10000 });
    await answerInput.click();
    await page.keyboard.press("Control+A");
    await page.keyboard.type(ANSWER_TEXT, { delay: 20 });
    await page.keyboard.press("Tab");
    await page.waitForTimeout(650);
  };

  const fillQuestion = async (questionNumber) => {
    await clickQuestionButton(page, questionNumber);
    await waitUntil(
      page,
      (text) =>
        text.includes(`进度：${questionNumber} / 10`) ||
        text.includes(`第 ${questionNumber} 题`),
      20000
    );

    await fillCurrentAnswer();
  };

  for (let questionNumber = 1; questionNumber <= 10; questionNumber += 1) {
    await fillQuestion(questionNumber);
  }

  for (let attempt = 0; attempt < 12; attempt += 1) {
    await clickQuestionButton(page, 10);
    await page.waitForTimeout(1000);
    const submitted = await clickVisibleButtonContaining(page, "提交试卷");
    if (!submitted) throw new Error("Submit button was not found.");

    const submitText = await waitUntil(
      page,
      (text) =>
        text.includes("作答结果") ||
        text.includes("系统正在阅卷") ||
        text.includes("题尚未作答"),
      30000
    );

    if (submitText.includes("作答结果") || submitText.includes("系统正在阅卷")) {
      break;
    }

    const unanswered = submitText.match(/第\s*(\d+)\s*题尚未作答/);
    if (!unanswered) {
      throw new Error("Submit did not enter grading and no unanswered question was reported.");
    }
    await fillQuestion(Number(unanswered[1]));
  }

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
  await editor.click();
  await componentFrame.page().keyboard.press("Control+A");
  await componentFrame.page().keyboard.press("Backspace");
  await componentFrame.page().waitForTimeout(180);
  await editor.evaluate((element) => {
    element.innerHTML = "";
    try {
      Object.keys(window.localStorage || {})
        .filter((key) => key.startsWith("controlled_hint_composer:"))
        .forEach((key) => window.localStorage.removeItem(key));
    } catch (_error) {
      // Some browser privacy modes can disable storage access.
    }
    element.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "deleteContentBackward" }));
  });
  await editor.click();
  // Clearing a large MathLive payload can trigger a Streamlit component remount.
  // Give that empty-state sync one short beat before the next scenario writes.
  await componentFrame.page().waitForTimeout(900);

  const state = await readComposerState(componentFrame);
  if (state.serializedText || state.latexValues.length > 0) {
    throw new Error(`Composer was not cleared before scenario: ${state.serializedText}`);
  }
}

async function clearComposerWithRetry(page, attempts = 3) {
  let lastError = null;

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const componentFrame = await getComponentFrame(page);
      await clearComposer(componentFrame);
      return await getComponentFrame(page);
    } catch (error) {
      lastError = error;
      if (!String(error.message).includes("Frame was detached")) throw error;
      await page.waitForTimeout(500);
    }
  }

  throw lastError || new Error("Composer could not be cleared.");
}

async function readComposerState(componentFrame) {
  const editor = await getEditor(componentFrame);
  const text = await editor.evaluate((element) => element.textContent || "");
  const html = await editor.evaluate((element) => element.innerHTML || "");
  const visibleText = await editor.evaluate((element) => element.innerText || "");
  const serializedText = await editor.evaluate((element) => {
    const zeroWidthSpace = "\u200B";
    let value = "";

    const getLatex = (mathField) => {
      if (!mathField) return "";
      try {
        const latex = mathField.getValue?.("latex-without-placeholders");
        if (typeof latex === "string") return latex;
      } catch (_error) {
        // Fall through to raw value for older MathLive versions.
      }
      return typeof mathField.value === "string" ? mathField.value : "";
    };

    const visit = (node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        value += (node.textContent || "").replaceAll(zeroWidthSpace, "");
        return;
      }

      if (!(node instanceof HTMLElement)) return;

      if (node.classList.contains("inline-formula-chip")) {
        const latex = getLatex(node.querySelector("math-field")).trim();
        if (latex) value += `$${latex}$`;
        return;
      }

      if (node.tagName === "BR") {
        value += "\n";
        return;
      }

      node.childNodes.forEach(visit);
    };

    element.childNodes.forEach(visit);
    return value;
  });
  const caretInfo = await editor.evaluate((element) => {
    const zeroWidthSpace = "\u200B";
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) {
      return { insideEditor: false, textOffset: null, isCollapsed: true };
    }

    const range = selection.getRangeAt(0);
    const insideEditor = element.contains(range.commonAncestorContainer);
    if (!insideEditor) {
      return { insideEditor: false, textOffset: null, isCollapsed: range.collapsed };
    }

    const preRange = range.cloneRange();
    preRange.selectNodeContents(element);
    preRange.setEnd(range.startContainer, range.startOffset);
    const textOffset = (preRange.toString() || "").replaceAll(
      zeroWidthSpace,
      ""
    ).length;
    return { insideEditor: true, textOffset, isCollapsed: range.collapsed };
  });
  const latexValues = await componentFrame
    .locator("math-field")
    .evaluateAll((fields) =>
      fields.map((field) =>
        field.getValue ? field.getValue("latex-without-placeholders") : field.value
      )
    );
  return { text, visibleText, serializedText, html, caretInfo, latexValues };
}

async function forceComposerFlush(page, componentFrame) {
  await componentFrame.locator("body").evaluate((body) => {
    body.dispatchEvent(new MouseEvent("mouseleave", { bubbles: true }));
    body.dispatchEvent(new PointerEvent("pointerleave", { bubbles: true }));
  });
  await page.mouse.move(8, 8);
  await page.waitForTimeout(550);
}

async function openToolbarGroup(componentFrame, name) {
  const group = componentFrame.getByRole("button", { name, exact: true });
  const isActive = await group
    .evaluate((button) => button.classList.contains("is-active"))
    .catch(() => false);
  if (isActive) return;

  await group.click();
  await componentFrame.page().waitForTimeout(350);
}

async function insertCasesFunction(componentFrame, segmentCount) {
  await openToolbarGroup(componentFrame, "函数");
  const casesSelect = componentFrame.locator('select[aria-label="插入分段函数"]');
  if ((await casesSelect.count()) === 0) throw new Error("Cases selector was not found.");

  await casesSelect.selectOption(String(segmentCount));
  await componentFrame.page().waitForTimeout(700);

  const state = await readComposerState(componentFrame);
  if (state.latexValues.some((value) => String(value).includes("\\begin{cases}"))) return;

  await casesSelect.evaluate((select, value) => {
    select.value = value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }, String(segmentCount));
  await componentFrame.page().waitForTimeout(700);
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

async function setCaretByTextOffset(componentFrame, offset) {
  const editor = await getEditor(componentFrame);
  await editor.evaluate((element, targetOffset) => {
    const zeroWidthSpace = "\u200B";
    const selection = window.getSelection();
    const range = document.createRange();
    let remaining = targetOffset;
    let targetNode = null;
    let targetNodeOffset = 0;

    const visit = (node) => {
      if (targetNode) return;

      if (node.nodeType === Node.TEXT_NODE) {
        const rawText = node.textContent || "";
        const normalizedText = rawText.replaceAll(zeroWidthSpace, "");
        if (remaining <= normalizedText.length) {
          let rawOffset = 0;
          let normalizedOffset = 0;
          while (rawOffset < rawText.length && normalizedOffset < remaining) {
            if (rawText[rawOffset] !== zeroWidthSpace) normalizedOffset += 1;
            rawOffset += 1;
          }
          targetNode = node;
          targetNodeOffset = rawOffset;
          return;
        }
        remaining -= normalizedText.length;
        return;
      }

      if (!(node instanceof HTMLElement)) return;
      if (node.classList.contains("inline-formula-chip")) return;
      node.childNodes.forEach(visit);
    };

    element.childNodes.forEach(visit);

    element.focus({ preventScroll: true });

    if (targetNode) {
      range.setStart(targetNode, targetNodeOffset);
    } else {
      range.selectNodeContents(element);
      range.collapse(false);
    }

    range.collapse(true);
    selection?.removeAllRanges();
    selection?.addRange(range);
  }, offset);
  await componentFrame.page().waitForTimeout(120);
}

async function typeInComposer(componentFrame, text, delay = 0) {
  const editor = await getEditor(componentFrame);
  await editor.click();
  await componentFrame.page().keyboard.type(text, { delay });
}

async function focusComposerEnd(componentFrame) {
  const editor = await getEditor(componentFrame);
  await editor.evaluate((element) => {
    element.focus();
    const range = document.createRange();
    range.selectNodeContents(element);
    range.collapse(false);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
  });
}

async function pressKeyRepeatedly(page, key, count, delay = 0) {
  for (let index = 0; index < count; index += 1) {
    await page.keyboard.press(key);
    if (delay > 0) await page.waitForTimeout(delay);
  }
}

async function insertFormula(componentFrame, latex, options = {}) {
  await componentFrame.getByRole("button", { name: /插入公式框/ }).click();
  await componentFrame.page().waitForTimeout(options.afterInsertWait ?? 500);
  const mathField = componentFrame.locator("math-field").last();
  await mathField.click();
  if (latex) {
    await componentFrame.page().keyboard.type(latex, {
      delay: options.typeDelay ?? 12,
    });
  }
  await componentFrame.page().waitForTimeout(options.finalWait ?? 550);
}

async function sendPromptAndWait(page, options = {}) {
  const clickedCount = await clickVisibleButtonContainingTimes(
    page,
    "发送",
    options.clickTimes || 1
  );
  if (clickedCount === 0) {
    const buttonDebug = await describeButtonsContaining(page, "发送");
    throw new Error(`Send button was not available after input. Candidates: ${JSON.stringify(buttonDebug)}`);
  }

  let generationStarted = false;
  const firstState = await waitUntil(
    page,
    (text) =>
      text.includes("正在生成智能辅导") ||
      text.includes("生成链路") ||
      text.includes("请输入辅导问题后再发送"),
    options.firstStateTimeout || 45000
  );

  if (firstState.includes("请输入辅导问题后再发送")) {
    throw new Error("Prompt was treated as empty or stale during send.");
  }
  if (
    !firstState.includes("正在生成智能辅导") &&
    !firstState.includes("生成链路")
  ) {
    throw new Error("Generation did not start after clicking send.");
  }
  generationStarted = true;

  const finalText = await waitForFinalSendState(page, options);

  const finalState = getReplyStateAfterPrompt(finalText, options.expectedPrompt);
  const finalReplyVisible = finalState.finalReplyVisible;
  const leakageStatusVisible = finalState.leakageStatusVisible;
  if (!finalReplyVisible || !leakageStatusVisible) {
    throw new Error("Real send did not render assistant output and leakage status.");
  }
  if (options.expectedPrompt && !finalText.includes(options.expectedPrompt)) {
    throw new Error(`Sent prompt marker was not visible: ${options.expectedPrompt}`);
  }
  const promptMarkerOccurrences = options.expectedPrompt
    ? finalText.split(options.expectedPrompt).length - 1
    : 0;
  if (options.expectedPrompt && promptMarkerOccurrences > 1) {
    throw new Error(
      `Prompt marker appeared more than once; possible duplicate submit: ${options.expectedPrompt}`
    );
  }

  return {
    send_clicked_count: clickedCount,
    generation_started: generationStarted,
    final_reply_visible: finalReplyVisible,
    leakage_status_visible: leakageStatusVisible,
    prompt_marker_occurrences: promptMarkerOccurrences,
  };
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
    let componentFrame = await clearComposerWithRetry(page);
    const runMeta = (await scenario.run(page, componentFrame)) || {};
    let state = { text: "", html: "", latexValues: [] };
    if (!scenario.skipFinalComposerRead) {
      try {
        await forceComposerFlush(page, componentFrame);
      } catch (error) {
        if (!String(error.message).includes("Frame was detached")) throw error;
      }
      componentFrame = await getComponentFrame(page);
      await forceComposerFlush(page, componentFrame);
      state = await readComposerState(componentFrame);
    }
    const assertMeta = (await scenario.assert(state, page, componentFrame)) || {};
    const meta = { ...runMeta, ...assertMeta };
    await page.screenshot({ path: screenshot, fullPage: true });
    results.push({
      scenario_id: scenario.id,
      input_type: scenario.type,
      caret_case: scenario.caretCase || meta.caret_case || null,
      expected_order: scenario.expectedOrder || meta.expected_order || null,
      passed: true,
      actual_text: state.serializedText || state.text,
      visible_text: state.visibleText,
      caret_info: state.caretInfo || null,
      latex_values: state.latexValues,
      send_clicked_count: meta.send_clicked_count || 0,
      generation_started: Boolean(meta.generation_started),
      final_reply_visible: Boolean(meta.final_reply_visible),
      leakage_status_visible: Boolean(meta.leakage_status_visible),
      elapsed_ms: Date.now() - startedAt,
      screenshot,
    });
  } catch (error) {
    if (
      String(error.message || "").includes("Frame was detached") &&
      !scenario.__frame_retry
    ) {
      await page.waitForTimeout(1000);
      return await runScenario(page, { ...scenario, __frame_retry: true }, results);
    }

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
      caret_case: scenario.caretCase || null,
      expected_order: scenario.expectedOrder || null,
      passed: false,
      error: error.message,
      actual_text: state.serializedText || state.text,
      visible_text: state.visibleText || "",
      caret_info: state.caretInfo || null,
      latex_values: state.latexValues || [],
      send_clicked_count: 0,
      generation_started: false,
      final_reply_visible: false,
      leakage_status_visible: false,
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
    caretCase: "continuous-input",
    run: async (_page, componentFrame) => {
      await typeInComposer(componentFrame, "你好 ABC 123，标点！🙂", 15);
    },
    assert: async (state) => {
      assertIncludes(state.text, "你好 ABC 123", "Plain text was not retained");
      assertIncludes(state.text, "🙂", "Emoji was not retained");
    },
  },
  {
    id: "rapid_chinese_continuous_input",
    type: "caret-text",
    caretCase: "fast-continuous-chinese",
    expectedOrder: "连续输入第一段第二段第三段",
    run: async (_page, componentFrame) => {
      await typeInComposer(componentFrame, "连续输入", 0);
      await componentFrame.page().keyboard.type("第一段", { delay: 0 });
      await componentFrame.page().keyboard.type("第二段", { delay: 0 });
      await componentFrame.page().keyboard.type("第三段", { delay: 0 });
    },
    assert: async (state) => {
      assertIncludes(
        state.serializedText,
        "连续输入第一段第二段第三段",
        "Continuous Chinese input order was not stable"
      );
    },
  },
  {
    id: "rapid_enter_retention",
    type: "caret-enter",
    caretCase: "fast-enter",
    expectedOrder: "第一行\\n第二行\\n\\n第四行",
    run: async (_page, componentFrame) => {
      await typeInComposer(componentFrame, "第一行", 0);
      await componentFrame.page().keyboard.press("Enter");
      await componentFrame.page().keyboard.type("第二行", { delay: 0 });
      await componentFrame.page().keyboard.press("Enter");
      await componentFrame.page().keyboard.press("Enter");
      await componentFrame.page().keyboard.type("第四行", { delay: 0 });
    },
    assert: async (state) => {
      assertIncludes(state.serializedText, "第一行", "First line was lost");
      assertIncludes(state.serializedText, "第二行", "Second line was lost");
      assertIncludes(state.serializedText, "第四行", "Fourth line was lost");
      if (!state.serializedText.includes("\n")) {
        throw new Error(`Line breaks were not serialized: ${state.serializedText}`);
      }
    },
  },
  {
    id: "rapid_backspace_delete_retype",
    type: "caret-delete",
    caretCase: "fast-backspace-delete",
    expectedOrder: "ABXY",
    run: async (_page, componentFrame) => {
      await typeInComposer(componentFrame, "ABCDE", 0);
      await pressKeyRepeatedly(componentFrame.page(), "Backspace", 3, 0);
      await componentFrame.page().keyboard.type("XY", { delay: 0 });
    },
    assert: async (state) => {
      assertIncludes(state.serializedText, "ABXY", "Fast backspace/retype order was not stable");
      if (state.serializedText.includes("CDE")) {
        throw new Error(`Deleted content reappeared: ${state.serializedText}`);
      }
    },
  },
  {
    id: "ctrl_a_replace",
    type: "caret-replace",
    caretCase: "ctrl-a-replace",
    expectedOrder: "替换后的新内容",
    run: async (_page, componentFrame) => {
      await typeInComposer(componentFrame, "旧内容不应该保留", 0);
      await componentFrame.page().keyboard.press("Control+A");
      await componentFrame.page().keyboard.type("替换后的新内容", { delay: 0 });
    },
    assert: async (state) => {
      assertIncludes(state.serializedText, "替换后的新内容", "Ctrl+A replacement was not retained");
      if (state.serializedText.includes("旧内容")) {
        throw new Error(`Old content was not replaced: ${state.serializedText}`);
      }
    },
  },
  {
    id: "middle_caret_insert_order",
    type: "caret-middle",
    caretCase: "middle-insert",
    expectedOrder: "前中后",
    run: async (_page, componentFrame) => {
      await typeInComposer(componentFrame, "前后", 0);
      await setCaretByTextOffset(componentFrame, 1);
      await componentFrame.page().keyboard.type("中", { delay: 0 });
    },
    assert: async (state) => {
      assertIncludes(state.serializedText, "前中后", "Middle caret insertion order was not stable");
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
      await focusComposerEnd(componentFrame);
      await componentFrame.page().keyboard.type(" 和 ", { delay: 15 });
      await focusComposerEnd(componentFrame);
      await insertFormula(componentFrame, "\\sqrt{x}");
    },
    assert: async (state) => {
      assertLatexIncludes(state.latexValues, "x^2", "First formula was not retained");
      assertLatexIncludes(state.latexValues, "\\sqrt{x}", "Second formula was not retained");
    },
  },
  {
    id: "formula_immediate_after_insert",
    type: "formula-immediate",
    caretCase: "formula-insert-no-wait",
    expectedOrder: "公式前$x+3$",
    run: async (_page, componentFrame) => {
      await typeInComposer(componentFrame, "公式前", 0);
      await insertFormula(componentFrame, "x+3", {
        afterInsertWait: 80,
        typeDelay: 0,
        finalWait: 0,
      });
    },
    assert: async (state) => {
      assertIncludes(state.serializedText, "公式前", "Text before immediate formula was not retained");
      assertLatexIncludes(state.latexValues, "x+3", "Immediate formula latex was not retained");
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
    id: "matrix_2x2_immediate",
    type: "matrix-immediate",
    caretCase: "matrix-insert-no-wait",
    run: async (_page, componentFrame) => {
      await insertMatrix(componentFrame, 2, 2);
      await componentFrame.page().keyboard.type("x", { delay: 0 });
    },
    assert: async (state) => {
      assertLatexIncludes(state.latexValues, "\\begin{pmatrix}", "2x2 matrix was not retained");
      const matrixLatex = state.latexValues.find((value) => String(value).includes("\\begin{pmatrix}")) || "";
      if (!matrixLatex.includes("&") || !matrixLatex.includes("\\\\")) {
        throw new Error(`2x2 matrix appears malformed: ${matrixLatex}`);
      }
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
      await insertCasesFunction(componentFrame, 3);
    },
    assert: async (state) => {
      assertLatexIncludes(state.latexValues, "\\begin{cases}", "Cases function was not retained");
    },
  },
  {
    id: "cases_function_5_segments",
    type: "cases",
    run: async (_page, componentFrame) => {
      await insertCasesFunction(componentFrame, 5);
    },
    assert: async (state) => {
      assertLatexIncludes(state.latexValues, "\\begin{cases}", "5-segment cases function was not retained");
      const casesLatex = state.latexValues.find((value) => String(value).includes("\\begin{cases}")) || "";
      if ((casesLatex.match(/\\\\/g) || []).length < 4) {
        throw new Error(`5-segment cases function appears truncated: ${casesLatex}`);
      }
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
      componentFrame = await getComponentFrame(page);
      await focusComposerEnd(componentFrame);
      await componentFrame.page().keyboard.type("，继续输入", { delay: 15 });
    },
    assert: async (state) => {
      assertIncludes(state.text, "点击外部后仍应保留，继续输入", "Refocus text was not retained");
    },
  },
  {
    id: "switch_question_retention",
    type: "page-state",
    caretCase: "switch-question-return",
    expectedOrder: "切题后回来仍然保留",
    run: async (page) => {
      await clickQuestionButton(page, 1);
      await waitUntil(page, (text) => text.includes("请求智能辅导") || text.includes("请在下方输入"), 30000);
      let componentFrame = await getComponentFrame(page);
      await clearComposer(componentFrame);
      componentFrame = await getComponentFrame(page);
      await typeInComposer(componentFrame, "切题后回来仍然保留", 0);
      await forceComposerFlush(page, componentFrame);
      await clickQuestionButton(page, 2);
      await waitUntil(page, (text) => text.includes("请求智能辅导") || text.includes("请在下方输入"), 30000);
      await clickQuestionButton(page, 1);
      await waitUntil(page, (text) => text.includes("请求智能辅导") || text.includes("请在下方输入"), 30000);
      await page.waitForTimeout(900);
    },
    assert: async (state) => {
      assertIncludes(state.serializedText, "切题后回来仍然保留", "Composer value was lost after question switch");
    },
  },
];

const realSendScenarios = [
  {
    id: "real_send_plain_immediate",
    type: "send",
    caretCase: "plain-input-send-immediately",
    skipFinalComposerRead: true,
    run: async (page, frame) => {
      const marker = `E2E_PLAIN_${Date.now()}`;
      await typeInComposer(frame, `连续中文输入后马上发送 ${marker}`, 0);
      return await sendPromptAndWait(page, { expectedPrompt: marker });
    },
    assert: async () => {},
  },
  {
    id: "real_send_enter_immediate",
    type: "send",
    caretCase: "enter-send-immediately",
    skipFinalComposerRead: true,
    run: async (page, frame) => {
      const marker = `E2E_ENTER_${Date.now()}`;
      await typeInComposer(frame, `第一行 ${marker}`, 0);
      await frame.page().keyboard.press("Enter");
      await frame.page().keyboard.type("第二行马上发送", { delay: 0 });
      return await sendPromptAndWait(page, { expectedPrompt: marker });
    },
    assert: async () => {},
  },
  {
    id: "real_send_delete_immediate",
    type: "send",
    caretCase: "delete-send-immediately",
    skipFinalComposerRead: true,
    run: async (page, frame) => {
      const marker = `E2E_DELETE_${Date.now()}`;
      await typeInComposer(frame, `${marker} 将要删除xxx`, 0);
      await pressKeyRepeatedly(frame.page(), "Backspace", 3, 0);
      await frame.page().keyboard.type("后马上发送", { delay: 0 });
      return await sendPromptAndWait(page, { expectedPrompt: marker });
    },
    assert: async () => {},
  },
  {
    id: "real_send_formula_immediate",
    type: "send",
    caretCase: "formula-send-immediately",
    skipFinalComposerRead: true,
    run: async (page, frame) => {
      const marker = `E2E_FORMULA_${Date.now()}`;
      await typeInComposer(frame, `公式后马上发送 ${marker} `, 0);
      await insertFormula(frame, "x^2+1", {
        afterInsertWait: 80,
        typeDelay: 0,
        finalWait: 0,
      });
      return await sendPromptAndWait(page, { expectedPrompt: marker });
    },
    assert: async () => {},
  },
  {
    id: "real_send_matrix_immediate",
    type: "send",
    caretCase: "matrix-send-immediately",
    skipFinalComposerRead: true,
    run: async (page, frame) => {
      const marker = `E2E_MATRIX_${Date.now()}`;
      await typeInComposer(frame, `矩阵后马上发送 ${marker} `, 0);
      await insertMatrix(frame, 2, 2);
      return await sendPromptAndWait(page, { expectedPrompt: marker });
    },
    assert: async () => {},
  },
  {
    id: "real_send_cases_immediate",
    type: "send",
    caretCase: "cases-send-immediately",
    skipFinalComposerRead: true,
    run: async (page, frame) => {
      const marker = `E2E_CASES_${Date.now()}`;
      await typeInComposer(frame, `分段函数后马上发送 ${marker} `, 0);
      await openToolbarGroup(frame, "函数");
      const casesSelect = frame.locator('select[aria-label="插入分段函数"]');
      if ((await casesSelect.count()) === 0) throw new Error("Cases selector was not found.");
      await casesSelect.selectOption("2");
      await frame.page().waitForTimeout(100);
      return await sendPromptAndWait(page, { expectedPrompt: marker });
    },
    assert: async () => {},
  },
  {
    id: "real_send_double_click",
    type: "send",
    caretCase: "fast-double-click-send",
    skipFinalComposerRead: true,
    run: async (page, frame) => {
      const marker = `E2E_DOUBLE_${Date.now()}`;
      await typeInComposer(frame, `快速双击发送稳定性 ${marker}`, 0);
      return await sendPromptAndWait(page, {
        expectedPrompt: marker,
        clickTimes: 2,
      });
    },
    assert: async () => {},
  },
  {
    id: "real_send_middle_insert",
    type: "send",
    caretCase: "middle-insert-send",
    skipFinalComposerRead: true,
    run: async (page, frame) => {
      const marker = `E2E_MIDDLE_${Date.now()}`;
      await typeInComposer(frame, `前后 ${marker}`, 0);
      await setCaretByTextOffset(frame, 1);
      await frame.page().keyboard.type("中", { delay: 0 });
      return await sendPromptAndWait(page, { expectedPrompt: marker });
    },
    assert: async () => {},
  },
  {
    id: "real_send_long_text",
    type: "send",
    caretCase: "long-text-send",
    skipFinalComposerRead: true,
    run: async (page, frame) => {
      const marker = `E2E_LONG_${Date.now()}`;
      const text = `长文本压力测试 ${marker} ` + "请保持提示启发性，不要泄露答案。".repeat(20);
      await typeInComposer(frame, text, 0);
      return await sendPromptAndWait(page, { expectedPrompt: marker });
    },
    assert: async () => {},
  },
  {
    id: "real_send_formula_mix",
    type: "send",
    caretCase: "text-formula-text-send",
    skipFinalComposerRead: true,
    run: async (page, frame) => {
      const marker = `E2E_MIX_${Date.now()}`;
      await typeInComposer(frame, `文字 ${marker} `, 0);
      await frame.page().waitForTimeout(COMPOSER_SYNC_SETTLE_MS);
      await insertFormula(frame, "\\sqrt{x}", {
        afterInsertWait: 80,
        typeDelay: 0,
        finalWait: 0,
      });
      await focusComposerEnd(frame);
      await frame.page().keyboard.type(" 公式后继续输入马上发送", { delay: 0 });
      return await sendPromptAndWait(page, { expectedPrompt: marker });
    },
    assert: async () => {},
  },
];

function selectedRealSendScenarios() {
  if (!RUN_REAL_SEND) return [];
  return realSendScenarios.filter(scenarioMatchesFilter);
}

async function maybeRunRealSendScenarios(page, results) {
  for (const scenario of selectedRealSendScenarios()) {
    await runScenario(page, scenario, results);
  }
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
    const selectedSendScenarios = selectedRealSendScenarios();
    if (selectedScenarios.length === 0 && selectedSendScenarios.length === 0) {
      throw new Error(
        `No E2E scenarios matched E2E_SCENARIO_FILTER=${JSON.stringify(
          SCENARIO_FILTER
        )}.`
      );
    }

    for (const scenario of selectedScenarios) {
      await runScenario(page, scenario, results);
    }
    await maybeRunRealSendScenarios(page, results);

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
