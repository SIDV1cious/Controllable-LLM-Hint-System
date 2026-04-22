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

const FRAME_HEIGHT = 620;

const MyComponent = ({ args }: ComponentProps) => {
  const mfRef = useRef<any>(null);
  const vkRef = useRef<any>(null);
  const [latex, setLatex] = useState(args.default_value || "");

  const refreshFrameHeight = () => {
    window.setTimeout(() => Streamlit.setFrameHeight(FRAME_HEIGHT), 0);
    window.setTimeout(() => Streamlit.setFrameHeight(FRAME_HEIGHT), 100);
  };

  useEffect(() => {
    vkRef.current = initVirtualKeyboardInCurrentBrowsingContext();
    refreshFrameHeight();
  }, []);

  useEffect(() => {
    const mf = mfRef.current;
    const vk = vkRef.current;

    if (!mf) return;

    mf.value = args.default_value || "";
    mf.mathVirtualKeyboardPolicy = "sandboxed";

    const handleInput = (e: any) => {
      const newValue = e.target.value;
      setLatex(newValue);
      Streamlit.setComponentValue(newValue);
    };

    const handleGeometryChange = () => {
      refreshFrameHeight();
    };

    mf.addEventListener("input", handleInput);

    if (vk) {
      vk.addEventListener("geometrychange", handleGeometryChange);
    }

    refreshFrameHeight();

    return () => {
      mf.removeEventListener("input", handleInput);
      if (vk) {
        vk.removeEventListener("geometrychange", handleGeometryChange);
      }
    };
  }, [args.default_value]);

  useEffect(() => {
    const style = document.createElement("style");
    style.innerHTML = `
      html, body {
        overflow: hidden !important;
      }

      math-virtual-keyboard {
        position: fixed !important;
        left: 0 !important;
        right: 0 !important;
        bottom: 0 !important;
        width: 100% !important;
        z-index: 2147483647 !important;
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
        padding: "15px",
        borderRadius: "8px",
        border: "1px solid #ccc",
        minHeight: "420px",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          fontSize: "14px",
          color: "#666",
          marginBottom: "10px",
          fontWeight: "bold",
        }}
      >
        📐 MathLive 面板
      </div>

      <math-field
        ref={mfRef}
        style={{
          fontSize: "24px",
          width: "100%",
          minHeight: "180px",
          outline: "none",
          border: "1px solid #ddd",
          borderRadius: "4px",
          padding: "10px",
          display: "block",
        }}
      ></math-field>

      <div
        style={{
          marginTop: "15px",
          fontSize: "12px",
          color: "#333",
          wordBreak: "break-all",
        }}
      >
        <strong>✨ 对应的 LaTeX 代码:</strong>
        <code style={{ marginLeft: "8px", color: "#4a90e2" }}>{latex}</code>
      </div>
    </div>
  );
};

export default withStreamlitConnection(MyComponent);