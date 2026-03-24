// ==UserScript==
// @name         JSON Multi-Field Form Autofill
// @namespace    https://github.com/YanhanLi/json-field-copy-tool
// @version      0.1.0
// @description  Expand accordion-style form rows and fill multiple fields from a JSON array.
// @author       YanhanLi
// @match        *://*/*
// @grant        GM_addStyle
// @grant        GM_setClipboard
// ==/UserScript==

(function () {
  "use strict";

  const FIELD_MAP = [
    { jsonKeys: ["title", "name", "prompt", "question"], label: "评分点", kind: "textarea" },
    { jsonKeys: ["type", "category"], label: "类型", kind: "select" },
    { jsonKeys: ["weight", "score", "points"], label: "得分", kind: "input" },
    { jsonKeys: ["source", "url"], label: "来源", kind: "textarea" },
    { jsonKeys: ["reference", "quote"], label: "引用", kind: "textarea" },
    { jsonKeys: ["description", "summary", "notes"], label: "说明", kind: "textarea" },
  ];

  const UI_ID = "json-field-copy-tool-autofill";

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function triggerInput(el, value) {
    const nativeSetter = Object.getOwnPropertyDescriptor(el.__proto__, "value")?.set;
    if (nativeSetter) {
      nativeSetter.call(el, value);
    } else {
      el.value = value;
    }
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.dispatchEvent(new Event("blur", { bubbles: true }));
  }

  function getRecordValue(record, keys) {
    for (const key of keys) {
      if (record[key] !== undefined && record[key] !== null && String(record[key]).trim()) {
        return String(record[key]).trim();
      }
    }
    return "";
  }

  function findAllRecordContainers() {
    const noElements = [...document.querySelectorAll("body *")]
      .filter(el => el.children.length === 0)
      .filter(el => /^NO\.\s*\d+/i.test((el.textContent || "").trim()));

    const containers = [];
    const seen = new Set();

    for (const noEl of noElements) {
      const container = noEl.closest("div, section, article, li");
      if (!container || seen.has(container)) continue;
      seen.add(container);
      containers.push(container);
    }

    return containers;
  }

  function sectionLooksExpanded(section) {
    return ["评分点", "类型", "得分", "来源", "引用", "说明"]
      .some(text => section.textContent && section.textContent.includes(text));
  }

  async function ensureExpanded(section) {
    if (sectionLooksExpanded(section)) return;

    const clickable = [...section.querySelectorAll("button, [role='button'], span, i, div")]
      .filter(el => {
        const text = (el.textContent || "").trim();
        const aria = (el.getAttribute("aria-label") || "").toLowerCase();
        const title = (el.getAttribute("title") || "").toLowerCase();
        return /展开|expand|more|chevron|down|up/.test(text + " " + aria + " " + title) ||
          el.querySelector("svg");
      });

    const candidate = clickable[clickable.length - 1];
    if (candidate) {
      candidate.click();
      await sleep(300);
    }
  }

  function labelElement(section, labelText) {
    return [...section.querySelectorAll("label, span, div, p")]
      .find(el => (el.textContent || "").replace(/\s+/g, "").includes(labelText));
  }

  function findFieldContainer(section, labelText) {
    const label = labelElement(section, labelText);
    if (!label) return null;

    let node = label.closest("div, section, article");
    while (node) {
      if (node.querySelector("textarea, input, [role='combobox'], select")) return node;
      node = node.parentElement?.closest("div, section, article") || null;
    }
    return label.parentElement;
  }

  function findInputByKind(container, kind) {
    if (!container) return null;
    if (kind === "textarea") {
      return container.querySelector("textarea") || container.querySelector("input");
    }
    if (kind === "input") {
      return container.querySelector("input") || container.querySelector("textarea");
    }
    if (kind === "select") {
      return container.querySelector("[role='combobox'], select, input");
    }
    return container.querySelector("textarea, input, select, [role='combobox']");
  }

  async function setSelectValue(control, value) {
    if (!control || !value) return;

    if (control.tagName === "SELECT") {
      const option = [...control.options].find(opt => opt.textContent.trim() === value || opt.value === value);
      if (option) {
        control.value = option.value;
        control.dispatchEvent(new Event("change", { bubbles: true }));
      }
      return;
    }

    control.click();
    await sleep(300);

    const option = [...document.querySelectorAll("[role='option'], .ant-select-item-option, li, div")]
      .find(el => (el.textContent || "").trim() === value);

    if (option) {
      option.click();
      await sleep(200);
      return;
    }

    if (control.tagName === "INPUT") {
      triggerInput(control, value);
      await sleep(100);
    }
  }

  async function fillSection(section, record) {
    await ensureExpanded(section);

    for (const field of FIELD_MAP) {
      const value = getRecordValue(record, field.jsonKeys);
      if (!value) continue;

      const container = findFieldContainer(section, field.label);
      const control = findInputByKind(container, field.kind);
      if (!control) continue;

      if (field.kind === "select") {
        await setSelectValue(control, value);
      } else {
        triggerInput(control, value);
      }

      await sleep(120);
    }
  }

  function normalizeRecords(payload) {
    if (Array.isArray(payload)) return payload;
    if (payload && typeof payload === "object") {
      for (const key of ["items", "records", "rows", "entries", "data", "rubrics"]) {
        if (Array.isArray(payload[key])) return payload[key];
      }
    }
    throw new Error("JSON 需要是数组，或对象里带 items/records/data/rubrics 等数组字段");
  }

  function createUI() {
    if (document.getElementById(UI_ID)) return;

    if (typeof GM_addStyle === "function") {
      GM_addStyle(`
        #${UI_ID} {
          position: fixed;
          right: 20px;
          bottom: 20px;
          width: 360px;
          z-index: 999999;
          background: rgba(255, 253, 249, 0.96);
          border: 1px solid #d9d1c5;
          border-radius: 16px;
          box-shadow: 0 16px 40px rgba(0, 0, 0, 0.12);
          padding: 14px;
          font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
        }
        #${UI_ID} h3 {
          margin: 0 0 8px;
          font-size: 16px;
        }
        #${UI_ID} textarea {
          width: 100%;
          min-height: 160px;
          resize: vertical;
          border-radius: 10px;
          border: 1px solid #d9d1c5;
          padding: 10px;
          box-sizing: border-box;
          font-size: 12px;
          line-height: 1.45;
        }
        #${UI_ID} .row {
          display: flex;
          gap: 8px;
          margin-top: 8px;
        }
        #${UI_ID} button {
          border: none;
          border-radius: 10px;
          background: #0f6d58;
          color: white;
          padding: 9px 12px;
          cursor: pointer;
          font-size: 12px;
          flex: 1;
        }
        #${UI_ID} .secondary {
          background: #efe6d9;
          color: #1f1f1f;
        }
        #${UI_ID} .status {
          margin-top: 8px;
          font-size: 12px;
          color: #666;
          line-height: 1.45;
          white-space: pre-wrap;
        }
      `);
    }

    const panel = document.createElement("div");
    panel.id = UI_ID;
    panel.innerHTML = `
      <h3>批量自动填表</h3>
      <textarea id="${UI_ID}-input" placeholder='把 JSON 粘到这里，例如 [{"index":"1","title":"..."}]'></textarea>
      <div class="row">
        <button id="${UI_ID}-fill">展开并填充</button>
        <button id="${UI_ID}-clipboard" class="secondary">读剪贴板</button>
      </div>
      <div class="status" id="${UI_ID}-status">说明：
1. 把 rubrics_all.json 粘进来
2. 点击“展开并填充”
3. 脚本会按 NO.1/NO.2... 顺序展开并回填字段</div>
    `;
    document.body.appendChild(panel);

    const input = panel.querySelector(`#${UI_ID}-input`);
    const status = panel.querySelector(`#${UI_ID}-status`);

    panel.querySelector(`#${UI_ID}-clipboard`).addEventListener("click", async () => {
      try {
        input.value = await navigator.clipboard.readText();
        status.textContent = "已读取剪贴板，可以直接开始填充。";
      } catch (err) {
        status.textContent = "读取剪贴板失败，请手动粘贴 JSON。";
      }
    });

    panel.querySelector(`#${UI_ID}-fill`).addEventListener("click", async () => {
      try {
        const raw = input.value.trim();
        if (!raw) throw new Error("请先粘贴 JSON");

        const payload = JSON.parse(raw);
        const records = normalizeRecords(payload);
        const sections = findAllRecordContainers();
        if (!sections.length) throw new Error("页面上没找到 NO. 开头的记录卡片");

        status.textContent = `准备填充 ${records.length} 条记录，已找到 ${sections.length} 个页面卡片...`;

        for (let i = 0; i < records.length && i < sections.length; i += 1) {
          status.textContent = `正在处理 NO. ${i + 1}...`;
          await fillSection(sections[i], records[i]);
        }

        status.textContent = `完成：已处理 ${Math.min(records.length, sections.length)} 条记录。`;
      } catch (err) {
        status.textContent = `失败：${err.message}`;
      }
    });
  }

  createUI();
})();
