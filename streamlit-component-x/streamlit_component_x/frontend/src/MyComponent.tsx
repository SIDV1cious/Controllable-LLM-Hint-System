import {
  Streamlit,
  withStreamlitConnection,
  ComponentProps,
} from "streamlit-component-lib";
import React, { useEffect, useRef, useState } from "react";
import { initVirtualKeyboardInCurrentBrowsingContext } from "mathlive";
import "mathlive";
import "mathlive/static.css";

declare global {
  namespace JSX {
    interface IntrinsicElements {
      "math-field": any;
    }
  }
}

const FRAME_HEIGHT = 560;
const MAX_MATRIX_SIZE = 5;

const COMMON_SYMBOLS = [
  { label: "x^2", latex: "x^2" },
  { label: "x_n", latex: "x_n" },
  { label: "分式", latex: "\\frac{}{}" },
  { label: "根号", latex: "\\sqrt{}" },
  { label: "积分", latex: "\\int_{}^{}" },
  { label: "求和", latex: "\\sum_{}^{}" },
  { label: "≤", latex: "\\le" },
  { label: "≥", latex: "\\ge" },
  { label: "≠", latex: "\\ne" },
  { label: "∞", latex: "\\infty" },
];

const ADVANCED_SYMBOLS = [
  { label: "lim", latex: "\\lim_{}" },
  { label: "lim x→0", latex: "\\lim_{x\\to 0}" },
  { label: "α", latex: "\\alpha" },
  { label: "β", latex: "\\beta" },
  { label: "γ", latex: "\\gamma" },
  { label: "δ", latex: "\\delta" },
  { label: "λ", latex: "\\lambda" },
  { label: "μ", latex: "\\mu" },
  { label: "π", latex: "\\pi" },
  { label: "θ", latex: "\\theta" },
  { label: "Ω", latex: "\\Omega" },
];

const MyComponent = ({ args }: ComponentProps) => {
  const mfRef = useRef<any>(null);
  const vkRef = useRef<any>(null);
  const [entryMode, setEntryMode] = useState<"math" | "text">("text");
  const [matrixRows, setMatrixRows] = useState(2);
  const [matrixCols, setMatrixCols] = useState(2);

  const refreshFrameHeight = () => {
    window.setTimeout(() => Streamlit.setFrameHeight(FRAME_HEIGHT), 0);
    window.setTimeout(() => Streamlit.setFrameHeight(FRAME_HEIGHT), 80);
  };

  const syncValue = () => {
    const mf = mfRef.current;
    if (mf) {
      Streamlit.setComponentValue(mf.value || "");
    }
  };

  const focusMathField = () => {
    window.setTimeout(() => mfRef.current?.focus(), 0);
  };

  const insertLatex = (latex: string) => {
    const mf = mfRef.current;
    if (!mf) return;
    mf.mode = "math";
    setEntryMode("math");
    mf.insert(latex);
    syncValue();
    focusMathField();
  };

  const switchMode = (mode: "math" | "text") => {
    const mf = mfRef.current;
    setEntryMode(mode);
    if (mf) {
      mf.mode = mode;
      focusMathField();
    }
  };

  const insertMatrix = () => {
    const rows = Math.min(Math.max(matrixRows, 1), MAX_MATRIX_SIZE);
    const cols = Math.min(Math.max(matrixCols, 1), MAX_MATRIX_SIZE);
    const body = Array.from({ length: rows }, () =>
      Array.from({ length: cols }, () => "").join(" & ")
    ).join(" \\\\ ");
    insertLatex(`\\begin{pmatrix}${body}\\end{pmatrix}`);
  };

  useEffect(() => {
    vkRef.current = initVirtualKeyboardInCurrentBrowsingContext();
    refreshFrameHeight();
  }, []);

  useEffect(() => {
    const mf = mfRef.current;
    const vk = vkRef.current;

    if (!mf) return;

    const nextValue = args.default_value || "";
    if (nextValue !== mf.value) {
      mf.value = nextValue;
      Streamlit.setComponentValue(nextValue);
    }

    mf.mathVirtualKeyboardPolicy = "sandboxed";
    mf.defaultMode = "text";
    mf.mode = entryMode;
    mf.menuItems = [];
    mf.maxMatrixCols = MAX_MATRIX_SIZE;
    mf.mathModeSpace = "\\;";
    mf.smartFence = true;
    mf.smartMode = true;
    mf.popoverPolicy = "off";
    mf.environmentPopoverPolicy = "off";

    const handleInput = (e: any) => {
      Streamlit.setComponentValue(e.target.value);
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        mf.insert(" \\\\ ");
        syncValue();
      }
    };

    const handleGeometryChange = () => {
      refreshFrameHeight();
    };

    mf.addEventListener("input", handleInput);
    mf.addEventListener("keydown", handleKeyDown);

    if (vk) {
      vk.addEventListener("geometrychange", handleGeometryChange);
    }

    refreshFrameHeight();

    return () => {
      mf.removeEventListener("input", handleInput);
      mf.removeEventListener("keydown", handleKeyDown);
      if (vk) {
        vk.removeEventListener("geometrychange", handleGeometryChange);
      }
    };
  }, [args.default_value]);

  useEffect(() => {
    const style = document.createElement("style");
    style.innerHTML = `
      html, body {
        margin: 0;
        padding: 0;
        overflow: hidden !important;
        background: white;
      }

      #root {
        height: 100%;
      }

      math-virtual-keyboard {
        position: fixed !important;
        left: 0 !important;
        right: 0 !important;
        bottom: 0 !important;
        width: 100% !important;
        z-index: 2147483647 !important;
      }

      math-field::part(menu-toggle) {
        display: none;
      }
    `;
    document.head.appendChild(style);

    return () => {
      document.head.removeChild(style);
    };
  }, []);

  return (
    <div
      style={{
        background: "white",
        border: "1px solid #d9dee8",
        borderRadius: "6px",
        padding: "10px",
        height: "500px",
        boxSizing: "border-box",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "8px",
          marginBottom: "8px",
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", gap: "6px" }}>
          <button
            type="button"
            onClick={() => switchMode("math")}
            style={modeButtonStyle(entryMode === "math")}
          >
            公式
          </button>
          <button
            type="button"
            onClick={() => switchMode("text")}
            style={modeButtonStyle(entryMode === "text")}
          >
            文字
          </button>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ fontSize: "12px", color: "#536075" }}>矩阵</span>
          <select
            value={matrixRows}
            onChange={(e) => setMatrixRows(Number(e.target.value))}
            style={selectStyle}
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n}行
              </option>
            ))}
          </select>
          <select
            value={matrixCols}
            onChange={(e) => setMatrixCols(Number(e.target.value))}
            style={selectStyle}
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n}列
              </option>
            ))}
          </select>
          <button type="button" onClick={insertMatrix} style={toolButtonStyle}>
            插入
          </button>
        </div>
      </div>

      <div style={toolbarStyle}>
        {COMMON_SYMBOLS.map((item) => (
          <button
            key={item.label}
            type="button"
            onClick={() => insertLatex(item.latex)}
            style={toolButtonStyle}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div style={toolbarStyle}>
        {ADVANCED_SYMBOLS.map((item) => (
          <button
            key={item.label}
            type="button"
            onClick={() => insertLatex(item.latex)}
            style={toolButtonStyle}
          >
            {item.label}
          </button>
        ))}
        <button type="button" onClick={() => insertLatex("\\;")} style={toolButtonStyle}>
          空格
        </button>
        <button type="button" onClick={() => insertLatex(" \\\\ ")} style={toolButtonStyle}>
          换行
        </button>
      </div>

      <math-field
        ref={mfRef}
        style={{
          width: "100%",
          height: "220px",
          minHeight: "220px",
          display: "block",
          boxSizing: "border-box",
          fontSize: "24px",
          border: "1px solid #d9dee8",
          borderRadius: "6px",
          padding: "12px",
          outline: "none",
          overflow: "auto",
          background: "white",
        }}
      ></math-field>
    </div>
  );
};

const toolbarStyle: React.CSSProperties = {
  display: "flex",
  gap: "6px",
  flexWrap: "wrap",
  marginBottom: "8px",
};

const toolButtonStyle: React.CSSProperties = {
  border: "1px solid #cfd6e3",
  background: "#f8fafc",
  color: "#263244",
  borderRadius: "6px",
  padding: "5px 9px",
  fontSize: "12px",
  cursor: "pointer",
  minHeight: "28px",
};

const selectStyle: React.CSSProperties = {
  border: "1px solid #cfd6e3",
  borderRadius: "6px",
  background: "white",
  color: "#263244",
  fontSize: "12px",
  height: "28px",
};

const modeButtonStyle = (active: boolean): React.CSSProperties => ({
  ...toolButtonStyle,
  background: active ? "#2563eb" : "#f8fafc",
  borderColor: active ? "#2563eb" : "#cfd6e3",
  color: active ? "white" : "#263244",
  fontWeight: active ? 700 : 500,
});

export default withStreamlitConnection(MyComponent);
