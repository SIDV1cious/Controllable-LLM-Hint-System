import {
  Streamlit,
  withStreamlitConnection,
  ComponentProps,
} from "streamlit-component-lib";
import React, { useEffect, useRef } from "react";
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

const FRAME_HEIGHT = 640;

const MyComponent = ({ args }: ComponentProps) => {
  const mfRef = useRef<any>(null);
  const vkRef = useRef<any>(null);

  const refreshFrameHeight = () => {
    window.setTimeout(() => Streamlit.setFrameHeight(FRAME_HEIGHT), 0);
    window.setTimeout(() => Streamlit.setFrameHeight(FRAME_HEIGHT), 80);
  };

  useEffect(() => {
    vkRef.current = initVirtualKeyboardInCurrentBrowsingContext();
    refreshFrameHeight();
  }, []);

  useEffect(() => {
    const mf = mfRef.current;
    const vk = vkRef.current;

    if (!mf) return;

    if ((args.default_value || "") !== mf.value) {
      mf.value = args.default_value || "";
    }

    mf.mathVirtualKeyboardPolicy = "sandboxed";

    const handleInput = (e: any) => {
      Streamlit.setComponentValue(e.target.value);
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
        border: "1px solid #ddd",
        borderRadius: "8px",
        padding: "12px",
        height: "520px",
        boxSizing: "border-box",
        overflow: "hidden",
      }}
    >
      <math-field
        ref={mfRef}
        style={{
          width: "100%",
          height: "300px",
          minHeight: "300px",
          display: "block",
          boxSizing: "border-box",
          fontSize: "28px",
          border: "1px solid #ddd",
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

export default withStreamlitConnection(MyComponent);