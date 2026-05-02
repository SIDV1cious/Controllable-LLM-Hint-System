import{r as be,a as Se,w as Ce,S as W}from"./react-Mb8gHB7f.js";import"./mathlive-C7j8vnu0.js";(function(){const a=document.createElement("link").relList;if(a&&a.supports&&a.supports("modulepreload"))return;for(const c of document.querySelectorAll('link[rel="modulepreload"]'))n(c);new MutationObserver(c=>{for(const d of c)if(d.type==="childList")for(const g of d.addedNodes)g.tagName==="LINK"&&g.rel==="modulepreload"&&n(g)}).observe(document,{childList:!0,subtree:!0});function s(c){const d={};return c.integrity&&(d.integrity=c.integrity),c.referrerPolicy&&(d.referrerPolicy=c.referrerPolicy),c.crossOrigin==="use-credentials"?d.credentials="include":c.crossOrigin==="anonymous"?d.credentials="omit":d.credentials="same-origin",d}function n(c){if(c.ep)return;c.ep=!0;const d=s(c);fetch(c.href,d)}})();var Y={exports:{}},k={};/**
 * @license React
 * react-jsx-runtime.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */var re;function Ee(){if(re)return k;re=1;var t=be(),a=Symbol.for("react.element"),s=Symbol.for("react.fragment"),n=Object.prototype.hasOwnProperty,c=t.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentOwner,d={key:!0,ref:!0,__self:!0,__source:!0};function g(h,b,M){var f,p={},R=null,N=null;M!==void 0&&(R=""+M),b.key!==void 0&&(R=""+b.key),b.ref!==void 0&&(N=b.ref);for(f in b)n.call(b,f)&&!d.hasOwnProperty(f)&&(p[f]=b[f]);if(h&&h.defaultProps)for(f in b=h.defaultProps,b)p[f]===void 0&&(p[f]=b[f]);return{$$typeof:a,type:h,key:R,ref:N,props:p,_owner:c.current}}return k.Fragment=s,k.jsx=g,k.jsxs=g,k}var oe;function Te(){return oe||(oe=1,Y.exports=Ee()),Y.exports}var x=Te(),m=be(),D={},ne;function Me(){if(ne)return D;ne=1;var t=Se();return D.createRoot=t.createRoot,D.hydrateRoot=t.hydrateRoot,D}var ke=Me();const ie=520,C=10,T="​",_="常用符号",se="hint-placeholder-style",Ae=[2,3,4,5],ce=[{title:"分式/上下标",items:[{label:"分式",latex:"\\frac{#?}{#?}"},{label:"斜分式",latex:"#?/#?"},{label:"连分式",latex:"\\cfrac{#?}{#?}"},{label:"倒数",latex:"\\frac{1}{#?}"},{label:"二项式",latex:"\\binom{#?}{#?}"},{label:"上标",latex:"#?^{#?}"},{label:"下标",latex:"#?_{#?}"},{label:"上下标",latex:"#?_{#?}^{#?}"},{label:"平方",latex:"#?^2"},{label:"立方",latex:"#?^3"},{label:"n次方",latex:"#?^{#?}"}]},{title:"根式",items:[{label:"平方根",latex:"\\sqrt{#?}"},{label:"n次根",latex:"\\sqrt[#?]{#?}"},{label:"三次根",latex:"\\sqrt[3]{#?}"},{label:"四次根",latex:"\\sqrt[4]{#?}"}]},{title:"积分",items:[{label:"不定积分",latex:"\\int #?\\,\\mathrm{d}#?"},{label:"定积分",latex:"\\int_{#?}^{#?}#?\\,\\mathrm{d}#?"},{label:"反常积分",latex:"\\int_{#?}^{\\infty}#?\\,\\mathrm{d}#?"},{label:"无穷积分",latex:"\\int_{-\\infty}^{+\\infty}#?\\,\\mathrm{d}#?"},{label:"二重积分",latex:"\\iint_{#?}#?\\,\\mathrm{d}#?"},{label:"三重积分",latex:"\\iiint_{#?}#?\\,\\mathrm{d}#?"},{label:"曲线积分",latex:"\\int_{#?}#?\\,\\mathrm{d}s"},{label:"闭曲线积分",latex:"\\oint_{#?}#?\\,\\mathrm{d}s"},{label:"曲面积分",latex:"\\iint_{#?}#?\\,\\mathrm{d}S"}]},{title:"运算",items:[{label:"求和",latex:"\\sum_{#?}^{#?}#?"},{label:"乘积",latex:"\\prod_{#?}^{#?}#?"},{label:"余积",latex:"\\coprod_{#?}^{#?}#?"},{label:"并集",latex:"\\bigcup_{#?}^{#?}#?"},{label:"交集",latex:"\\bigcap_{#?}^{#?}#?"},{label:"最大值",latex:"\\max_{#?}#?"},{label:"最小值",latex:"\\min_{#?}#?"},{label:"上确界",latex:"\\sup_{#?}#?"},{label:"下确界",latex:"\\inf_{#?}#?"},{label:"limsup",latex:"\\limsup_{#?\\to#?}#?"},{label:"liminf",latex:"\\liminf_{#?\\to#?}#?"},{label:"argmax",latex:"\\operatorname*{arg\\,max}_{#?}#?"},{label:"argmin",latex:"\\operatorname*{arg\\,min}_{#?}#?"}]},{title:"括号",items:[{label:"圆括号",latex:"\\left(#?\\right)"},{label:"方括号",latex:"\\left[#?\\right]"},{label:"大括号",latex:"\\left\\{#?\\right\\}"},{label:"绝对值",latex:"\\left|#?\\right|"},{label:"范数",latex:"\\left\\|#?\\right\\|"},{label:"尖括号",latex:"\\left\\langle #?\\right\\rangle"},{label:"向下取整",latex:"\\left\\lfloor #?\\right\\rfloor"},{label:"向上取整",latex:"\\left\\lceil #?\\right\\rceil"},{label:"开区间",latex:"\\left(#?,#?\\right)"},{label:"闭区间",latex:"\\left[#?,#?\\right]"},{label:"左闭右开",latex:"\\left[#?,#?\\right)"},{label:"左开右闭",latex:"\\left(#?,#?\\right]"}]},{title:"函数",items:[{label:"sin",latex:"\\sin(#?)"},{label:"cos",latex:"\\cos(#?)"},{label:"tan",latex:"\\tan(#?)"},{label:"cot",latex:"\\cot(#?)"},{label:"sec",latex:"\\sec(#?)"},{label:"csc",latex:"\\csc(#?)"},{label:"arcsin",latex:"\\arcsin(#?)"},{label:"arccos",latex:"\\arccos(#?)"},{label:"arctan",latex:"\\arctan(#?)"},{label:"sinh",latex:"\\sinh(#?)"},{label:"cosh",latex:"\\cosh(#?)"},{label:"tanh",latex:"\\tanh(#?)"},{label:"ln",latex:"\\ln(#?)"},{label:"log",latex:"\\log_{#?}{#?}"},{label:"exp",latex:"\\exp(#?)"},{label:"e指数",latex:"e^{#?}"},{label:"函数值",latex:"#?(#?)"},{label:"复合函数",latex:"#?\\left(#?(#?)\\right)"},{label:"极限",latex:"\\lim_{#?\\to#?}#?"},{label:"左极限",latex:"\\lim_{#?\\to#?^-}#?"},{label:"右极限",latex:"\\lim_{#?\\to#?^+}#?"},{label:"无穷极限",latex:"\\lim_{#?\\to\\infty}#?"},{label:"分段函数",kind:"cases"}]},{title:"导数",items:[{label:"导数",latex:"\\frac{\\mathrm{d}}{\\mathrm{d}#?}#?"},{label:"一阶导",latex:"\\frac{\\mathrm{d}#?}{\\mathrm{d}#?}"},{label:"二阶导",latex:"\\frac{\\mathrm{d}^2#?}{\\mathrm{d}#?^2}"},{label:"n阶导",latex:"\\frac{\\mathrm{d}^{#?}}{\\mathrm{d}#?^{#?}}#?"},{label:"偏导",latex:"\\frac{\\partial}{\\partial #?}#?"},{label:"偏导数",latex:"\\frac{\\partial #?}{\\partial #?}"},{label:"二阶偏导",latex:"\\frac{\\partial^2 #?}{\\partial #?^2}"},{label:"n阶偏导",latex:"\\frac{\\partial^{#?}}{\\partial #?^{#?}}#?"},{label:"撇号导数",latex:"#?'"},{label:"二阶撇号",latex:"#?''"},{label:"微分",latex:"\\mathrm{d}#?"},{label:"梯度",latex:"\\nabla #?"},{label:"散度",latex:"\\nabla\\cdot #?"},{label:"旋度",latex:"\\nabla\\times #?"},{label:"拉普拉斯",latex:"\\Delta #?"}]},{title:"标注",items:[{label:"向量",latex:"\\vec{#?}"},{label:"帽子",latex:"\\hat{#?}"},{label:"宽帽",latex:"\\widehat{#?}"},{label:"波浪",latex:"\\tilde{#?}"},{label:"宽波浪",latex:"\\widetilde{#?}"},{label:"上划线",latex:"\\overline{#?}"},{label:"下划线",latex:"\\underline{#?}"},{label:"点",latex:"\\dot{#?}"},{label:"二重点",latex:"\\ddot{#?}"},{label:"共轭",latex:"\\overline{#?}"},{label:"实部",latex:"\\Re(#?)"},{label:"虚部",latex:"\\Im(#?)"},{label:"右箭头",latex:"\\overrightarrow{#?}"},{label:"左箭头",latex:"\\overleftarrow{#?}"}]}],Ne=[{label:"±",latex:"\\pm"},{label:"∓",latex:"\\mp"},{label:"∞",latex:"\\infty"},{label:"=",latex:"="},{label:"≠",latex:"\\ne"},{label:"≈",latex:"\\approx"},{label:"≅",latex:"\\cong"},{label:"∝",latex:"\\propto"},{label:"≡",latex:"\\equiv"},{label:"∼",latex:"\\sim"},{label:"≃",latex:"\\simeq"},{label:"≪",latex:"\\ll"},{label:"≫",latex:"\\gg"},{label:"×",latex:"\\times"},{label:"÷",latex:"\\div"},{label:"·",latex:"\\cdot"},{label:"∗",latex:"\\ast"},{label:"≤",latex:"\\le"},{label:"≥",latex:"\\ge"},{label:"<",latex:"<"},{label:">",latex:">"},{label:"∈",latex:"\\in"},{label:"∉",latex:"\\notin"},{label:"⊂",latex:"\\subset"},{label:"⊆",latex:"\\subseteq"},{label:"⊃",latex:"\\supset"},{label:"⊇",latex:"\\supseteq"},{label:"∪",latex:"\\cup"},{label:"∩",latex:"\\cap"},{label:"∖",latex:"\\setminus"},{label:"∅",latex:"\\varnothing"},{label:"N",latex:"\\mathbb{N}"},{label:"Z",latex:"\\mathbb{Z}"},{label:"Q",latex:"\\mathbb{Q}"},{label:"R",latex:"\\mathbb{R}"},{label:"C",latex:"\\mathbb{C}"},{label:"∀",latex:"\\forall"},{label:"∃",latex:"\\exists"},{label:"∄",latex:"\\nexists"},{label:"∧",latex:"\\land"},{label:"∨",latex:"\\lor"},{label:"¬",latex:"\\neg"},{label:"∴",latex:"\\therefore"},{label:"∵",latex:"\\because"},{label:"←",latex:"\\leftarrow"},{label:"→",latex:"\\rightarrow"},{label:"↔",latex:"\\leftrightarrow"},{label:"⇒",latex:"\\Rightarrow"},{label:"⇔",latex:"\\Leftrightarrow"},{label:"↦",latex:"\\mapsto"},{label:"∂",latex:"\\partial"},{label:"∇",latex:"\\nabla"},{label:"⊥",latex:"\\perp"},{label:"∥",latex:"\\parallel"},{label:"°",latex:"^\\circ"},{label:"α",latex:"\\alpha"},{label:"β",latex:"\\beta"},{label:"γ",latex:"\\gamma"},{label:"δ",latex:"\\delta"},{label:"ε",latex:"\\varepsilon"},{label:"ζ",latex:"\\zeta"},{label:"η",latex:"\\eta"},{label:"θ",latex:"\\theta"},{label:"κ",latex:"\\kappa"},{label:"λ",latex:"\\lambda"},{label:"μ",latex:"\\mu"},{label:"ν",latex:"\\nu"},{label:"ξ",latex:"\\xi"},{label:"π",latex:"\\pi"},{label:"ρ",latex:"\\rho"},{label:"σ",latex:"\\sigma"},{label:"τ",latex:"\\tau"},{label:"φ",latex:"\\varphi"},{label:"χ",latex:"\\chi"},{label:"ψ",latex:"\\psi"},{label:"ω",latex:"\\omega"},{label:"Γ",latex:"\\Gamma"},{label:"Δ",latex:"\\Delta"},{label:"Θ",latex:"\\Theta"},{label:"Λ",latex:"\\Lambda"},{label:"Π",latex:"\\Pi"},{label:"Σ",latex:"\\Sigma"},{label:"Φ",latex:"\\Phi"},{label:"Ω",latex:"\\Omega"}],Le=t=>`\\begin{cases}${Array.from({length:t},()=>"#?, & #?").join(" \\\\ ")}\\end{cases}`,Ie=({args:t})=>{const a=m.useRef(null),s=m.useRef(null),n=m.useRef({}),c=m.useRef(null),d=m.useRef(t.default_value||""),g=m.useRef(0),[h,b]=m.useState(1),[M,f]=m.useState(1),[p,R]=m.useState(null),N=()=>`formula_${Date.now()}_${g.current++}`,j=()=>{window.setTimeout(()=>W.setFrameHeight(ie),0),window.setTimeout(()=>W.setFrameHeight(ie),80)},q=e=>{const l=a.current;return!!l&&!!e&&l.contains(e)},L=()=>{const e=window.getSelection();if(!e||e.rangeCount===0)return;const l=e.getRangeAt(0);q(l.commonAncestorContainer)&&(A(l.commonAncestorContainer)||(s.current=l.cloneRange()))},y=e=>{c.current=e;const l=a.current;l&&l.querySelectorAll(".inline-formula-chip").forEach(r=>{r.classList.toggle("active",r.dataset.formulaId===e)})},H=()=>{const e=a.current;if(!e)return null;const l=window.getSelection();if(l&&l.rangeCount>0&&q(l.getRangeAt(0).commonAncestorContainer)){const o=l.getRangeAt(0),u=A(o.commonAncestorContainer);if(!u)return o;const i=document.createRange();return i.setStartAfter(u),i.collapse(!0),i}if(s.current&&q(s.current.commonAncestorContainer)&&!A(s.current.commonAncestorContainer))return s.current.cloneRange();const r=document.createRange();return r.selectNodeContents(e),r.collapse(!1),r},K=e=>{const l=window.getSelection();if(!l)return;const r=document.createRange();r.setStartAfter(e),r.collapse(!0),l.removeAllRanges(),l.addRange(r),s.current=r.cloneRange()},v=()=>{const e=a.current;if(!e)return;const l=Pe(e);d.current=l,W.setComponentValue(l),j()},Z=e=>{const l=e.nextSibling,r=e.previousSibling;X(l)&&l.remove(),X(r)&&r.remove(),e.remove(),v();const o=a.current;if(!o)return;o.focus();const u=document.createRange();u.selectNodeContents(o),u.collapse(!1);const i=window.getSelection();i==null||i.removeAllRanges(),i==null||i.addRange(u),s.current=u.cloneRange()},Q=(e="")=>{const l=N(),r=document.createElement("span");r.className="inline-formula-chip",r.dataset.formulaId=l,r.dataset.latex=e,r.contentEditable="false";const o=document.createElement("math-field");o.className="inline-formula-field",o.value=e,o.setAttribute("math-virtual-keyboard-policy","manual"),o.setAttribute("max-matrix-cols",String(C));const u=document.createElement("button");return u.type="button",u.className="inline-formula-remove",u.textContent="x",u.title="删除公式框",r.append(o,u),n.current[l]=o,r.addEventListener("mousedown",i=>{i.stopPropagation(),y(l)}),r.addEventListener("click",()=>{y(l),o.focus(),window.setTimeout(()=>me(o),0)}),o.addEventListener("focus",()=>{y(l)}),o.addEventListener("blur",()=>{De(o),r.dataset.latex=E(o,"latex"),v()}),o.addEventListener("keydown",i=>{i.stopPropagation()}),o.addEventListener("input",i=>{i.stopPropagation(),r.dataset.latex=E(o,"latex"),v()}),u.addEventListener("mousedown",i=>{i.preventDefault(),i.stopPropagation()}),u.addEventListener("click",i=>{i.preventDefault(),i.stopPropagation(),delete n.current[l],Z(r)}),window.setTimeout(()=>J(o),0),{id:l,chip:r,mathField:o}},F=e=>{const l=H();if(!l)return;l.deleteContents();const r=document.createTextNode(e);l.insertNode(r),K(r),v()},ee=(e="")=>{const l=a.current,r=H();if(!l||!r)return;const{id:o,chip:u,mathField:i}=Q(""),S=document.createTextNode(T);r.deleteContents(),r.insertNode(S),r.insertNode(u),K(S),y(o),v(),window.setTimeout(()=>{i.focus(),e&&(ue(i,e),u.dataset.latex=E(i,"latex"),v())},0)},ye=()=>{var ae;const e=c.current,l=e?n.current[e]:null;if(l!=null&&l.isConnected)return l;const r=window.getSelection();if(r&&r.rangeCount>0){const V=A(r.getRangeAt(0).commonAncestorContainer),U=(V==null?void 0:V.dataset.formulaId)||null,P=U?n.current[U]:null;if(P!=null&&P.isConnected)return y(U),P}const o=A(document.activeElement),u=(o==null?void 0:o.dataset.formulaId)||null,i=u?n.current[u]:null;if(i!=null&&i.isConnected)return y(u),i;const S=(ae=a.current)==null?void 0:ae.querySelector(".inline-formula-chip.active"),z=(S==null?void 0:S.dataset.formulaId)||null,I=z?n.current[z]:null;return I!=null&&I.isConnected?(y(z),I):null},B=e=>{const l=ye();if(!l){ee(e);return}ue(l,e);const r=l.closest(".inline-formula-chip");r&&(r.dataset.latex=E(l,"latex")),v()},ve=()=>{const e=Math.min(Math.max(h,1),C),l=Math.min(Math.max(M,1),C),r=Array.from({length:e},()=>Array.from({length:l},()=>"#?").join(" & ")).join(" \\\\ ");B(`\\begin{pmatrix}${r}\\end{pmatrix}`)},te=e=>{const l=H();if(!l||!l.collapsed)return!1;const r=e==="backward"?je(l):qe(l),o=Oe(r);return o?(delete n.current[o.dataset.formulaId||""],Z(o),!0):!1},we=e=>{if(e.key==="Enter"){e.preventDefault(),F(`
`);return}if(e.key==="Backspace"&&te("backward")){e.preventDefault();return}e.key==="Delete"&&te("forward")&&e.preventDefault()},_e=e=>{const l=e.clipboardData.getData("text/plain");l&&(e.preventDefault(),F(l))},Re=e=>{const l=a.current;if(!l)return;n.current={},l.innerHTML="";const r=/\$([^$]*)\$/g;let o=0,u;for(;(u=r.exec(e))!==null;){u.index>o&&l.append(document.createTextNode(e.slice(o,u.index)));const{chip:i}=Q(u[1]);l.append(i,document.createTextNode(T)),o=u.index+u[0].length}o<e.length&&l.append(document.createTextNode(e.slice(o))),y(null),j()};m.useEffect(()=>{Re(t.default_value||""),d.current=t.default_value||""},[]),m.useEffect(()=>{const e=document.createElement("style");return e.innerHTML=`
      html, body {
        margin: 0;
        padding: 0;
        overflow: hidden !important;
        background: white;
      }

      .mixed-editor {
        caret-color: #111827;
      }

      .mixed-editor:focus {
        border-color: #2563eb;
        box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.10);
      }

      button:focus,
      button:focus-visible {
        outline: none !important;
        box-shadow: none !important;
      }

      .formula-toolbar-button,
      .formula-toolbar-button:hover,
      .formula-toolbar-button:active,
      .formula-toolbar-button:focus,
      .formula-toolbar-button:focus-visible {
        border: 1px solid #cfd6e3 !important;
        outline: none !important;
        box-shadow: none !important;
      }

      .formula-toolbar-button.is-active,
      .formula-toolbar-button.is-active:hover,
      .formula-toolbar-button.is-active:active,
      .formula-toolbar-button.is-active:focus,
      .formula-toolbar-button.is-active:focus-visible {
        border: 1px solid #2563eb !important;
        color: #1d4ed8 !important;
        background-color: #eff6ff !important;
      }

      .inline-formula-chip {
        display: inline-flex;
        align-items: center;
        vertical-align: baseline;
        max-width: min(340px, 80vw);
        min-width: 92px;
        min-height: 34px;
        margin: 0 3px;
        padding: 2px 5px;
        border: 1px solid #a3a3a3;
        border-radius: 2px;
        background: #eeeeee;
        box-sizing: border-box;
        white-space: nowrap;
      }

      .inline-formula-chip.active {
        border-color: #2563eb;
        box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
        background: #f8fbff;
      }

      .inline-formula-field {
        display: inline-block;
        width: 100%;
        min-width: 72px;
        max-width: 300px;
        min-height: 28px;
        border: 0;
        padding: 2px 4px;
        background: transparent;
        font-size: 18px;
        outline: none;
        overflow-x: auto;
      }

      .inline-formula-field::part(menu-toggle),
      .inline-formula-field::part(virtual-keyboard-toggle) {
        display: none;
      }

      .inline-formula-field::part(placeholder) {
        display: inline-block;
        min-width: 0.9em;
        min-height: 0.9em;
        padding: 0 0.14em;
        color: #1d4ed8 !important;
        background: rgba(37, 99, 235, 0.22) !important;
        border: 1px solid #2563eb;
        border-radius: 3px;
        box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.16);
        text-align: center;
      }

      .inline-formula-remove {
        flex: 0 0 auto;
        width: 18px;
        height: 22px;
        margin-left: 2px;
        border: 0;
        border-left: 1px solid #c7c7c7;
        background: transparent;
        color: #6b7280;
        cursor: pointer;
        font-size: 14px;
        line-height: 1;
      }

      .inline-formula-remove:hover {
        color: #b91c1c;
      }
    `,document.head.appendChild(e),j(),()=>{document.head.removeChild(e)}},[]);const $=ce.find(e=>e.title===p),le=p===_?Ne:($==null?void 0:$.items)??[];return x.jsxs("div",{style:He,children:[x.jsxs("div",{style:Be,children:[x.jsx("button",{type:"button",onMouseDown:e=>e.preventDefault(),onClick:()=>ee(),style:Ve,children:"插入公式框"}),ce.map(e=>x.jsx("button",{className:`formula-toolbar-button${p===e.title?" is-active":""}`,type:"button",onMouseDown:l=>l.preventDefault(),onClick:l=>{l.currentTarget.blur(),R(r=>r===e.title?null:e.title)},style:{...de,...p===e.title?xe:{}},children:e.title},e.title)),x.jsx("button",{className:`formula-toolbar-button${p===_?" is-active":""}`,type:"button",onMouseDown:e=>e.preventDefault(),onClick:e=>{e.currentTarget.blur(),R(l=>l===_?null:_)},style:{...de,...p===_?xe:{}},children:_}),x.jsxs("div",{style:$e,children:[x.jsx("span",{style:{fontSize:"12px",color:"#536075"},children:"矩阵"}),x.jsx("select",{value:h,onChange:e=>b(Number(e.target.value)),onMouseDown:e=>e.stopPropagation(),style:G,children:Array.from({length:C},(e,l)=>l+1).map(e=>x.jsxs("option",{value:e,children:[e,"行"]},e))}),x.jsx("select",{value:M,onChange:e=>f(Number(e.target.value)),onMouseDown:e=>e.stopPropagation(),style:G,children:Array.from({length:C},(e,l)=>l+1).map(e=>x.jsxs("option",{value:e,children:[e,"列"]},e))}),x.jsx("button",{type:"button",onMouseDown:e=>e.preventDefault(),onClick:ve,style:ge,children:"插入矩阵"})]})]}),p&&le.length>0&&x.jsx("div",{style:p===_?ze:fe,children:le.map(e=>e.kind==="cases"?x.jsxs("select",{defaultValue:"","aria-label":"插入分段函数",onMouseDown:l=>l.stopPropagation(),onChange:l=>{const r=Number(l.currentTarget.value);r&&B(Le(r)),l.currentTarget.value=""},style:We,children:[x.jsx("option",{value:"",disabled:!0,hidden:!0,children:e.label}),Ae.map(l=>x.jsxs("option",{value:l,children:[l,"段"]},l))]},`${p}-${e.label}-cases`):x.jsx("button",{type:"button",onMouseDown:l=>l.preventDefault(),onClick:()=>e.latex&&B(e.latex),style:Ue,children:e.label},`${p}-${e.label}-${e.latex}`))}),x.jsx("div",{ref:a,className:"mixed-editor",contentEditable:!0,suppressContentEditableWarning:!0,onFocus:()=>{y(null),L()},onMouseUp:L,onKeyUp:L,onInput:()=>{L(),v()},onKeyDown:we,onPaste:_e,style:Ye})]})},Pe=t=>{let a="";const s=n=>{if(n.nodeType===Node.TEXT_NODE){a+=(n.textContent||"").replaceAll(T,"");return}if(n instanceof HTMLElement){if(n.classList.contains("inline-formula-chip")){const c=n.querySelector("math-field"),d=E(c,"latex-without-placeholders",n.dataset.latex||"").trim();d&&(a+=`$${d}$`);return}if(n.tagName==="BR"){a+=`
`;return}n.childNodes.forEach(s)}};return t.childNodes.forEach(s),a},E=(t,a="latex",s="")=>{var n;if(!t)return s;try{const c=(n=t.getValue)==null?void 0:n.call(t,a);if(typeof c=="string")return c}catch{}return typeof t.value=="string"?t.value:s},ue=(t,a)=>{J(t),t.focus(),t.insert(a,{mode:"math",format:"latex",selectionMode:"placeholder",focus:!0}),a.includes("\\placeholder[")&&window.setTimeout(()=>me(t),0)},J=(t,a=0)=>{if(!t.isConnected){a<10&&window.setTimeout(()=>J(t,a+1),30);return}w(()=>{t.defaultMode="math"}),w(()=>{t.mathVirtualKeyboardPolicy="manual"}),w(()=>{t.smartFence=!0}),w(()=>{t.maxMatrixCols=C}),w(()=>{t.menuItems=[]}),pe(t)},w=t=>{try{t()}catch{}},pe=(t,a=0)=>{w(()=>{t.style.setProperty("--placeholder-color","#1d4ed8"),t.style.setProperty("--placeholder-opacity","1")});const s=t.shadowRoot;if(!s){a<10&&window.setTimeout(()=>pe(t,a+1),30);return}if(s.getElementById(se))return;const n=document.createElement("style");n.id=se,n.textContent=`
    [part='placeholder'],
    .ML__placeholder {
      display: inline-block !important;
      min-width: 0.9em !important;
      min-height: 0.9em !important;
      opacity: 1 !important;
      color: #1d4ed8 !important;
      background: rgba(37, 99, 235, 0.22) !important;
      border: 1px solid #2563eb !important;
      border-radius: 3px !important;
      box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.16) !important;
      box-sizing: border-box !important;
      padding: 0 0.14em !important;
      text-align: center !important;
      cursor: text !important;
      pointer-events: auto !important;
    }

    [part='placeholder'].ML__placeholder-selected,
    .ML__placeholder-selected,
    .ML__selected .ML__placeholder {
      background: rgba(37, 99, 235, 0.34) !important;
      box-shadow: 0 0 0 1px #2563eb inset;
    }
  `,s.appendChild(n)},me=t=>{w(()=>{var c,d;const a=(c=t.getPrompts)==null?void 0:c.call(t,{locked:!1}),s=Array.isArray(a)?a[0]:null,n=s?(d=t.getPromptRange)==null?void 0:d.call(t,s):null;n&&(t.focus(),t.selection=n)})},De=t=>{w(()=>{var c,d;const a=(c=t.getPrompts)==null?void 0:c.call(t,{locked:!1});if(!Array.isArray(a)||a.length===0||a.some(g=>{var b;const h=(b=t.getPromptValue)==null?void 0:b.call(t,g,"latex-without-placeholders");return!String(h||"").trim()}))return;const n=E(t,"latex-without-placeholders").trim();n&&((d=t.setValue)==null||d.call(t,n,{selectionMode:"after",silenceNotifications:!0}))})},X=t=>(t==null?void 0:t.nodeType)===Node.TEXT_NODE&&(t.textContent||"").replaceAll(T,"")==="",O=t=>t instanceof HTMLElement&&t.classList.contains("inline-formula-chip"),A=t=>{if(!t)return null;if(O(t))return t;const a=t instanceof HTMLElement?t:t.parentElement||null;return(a==null?void 0:a.closest(".inline-formula-chip"))||null},Oe=t=>{if(O(t))return t;if(X(t)){if(O(t.previousSibling))return t.previousSibling;if(O(t.nextSibling))return t.nextSibling}return null},je=t=>{const{startContainer:a,startOffset:s}=t;return a.nodeType===Node.TEXT_NODE?(a.textContent||"").slice(0,s).replaceAll(T,"")===""?a.previousSibling:null:a.childNodes[s-1]||null},qe=t=>{const{startContainer:a,startOffset:s}=t;return a.nodeType===Node.TEXT_NODE?(a.textContent||"").slice(s).replaceAll(T,"")===""?a.nextSibling:null:a.childNodes[s]||null},He={background:"white",border:"1px solid #d9dee8",borderRadius:"8px",padding:"10px",height:"485px",boxSizing:"border-box",overflow:"hidden"},Be={display:"flex",gap:"5px",flexWrap:"wrap",alignItems:"center",marginBottom:"8px"},$e={display:"flex",alignItems:"center",gap:"5px",flex:"0 0 auto",flexWrap:"nowrap",marginLeft:"auto"},de={border:"1px solid #cfd6e3",backgroundColor:"#f8fafc",backgroundImage:`url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' fill='none' stroke='%23536075' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")`,backgroundRepeat:"no-repeat",backgroundPosition:"right 7px center",backgroundSize:"10px 6px",color:"#263244",borderRadius:"7px",padding:"6px 21px 6px 8px",display:"flex",alignItems:"center",fontSize:"12px",cursor:"pointer",flex:"0 0 auto",minHeight:"30px",outline:"none",listStyle:"none"},xe={borderColor:"#2563eb",color:"#1d4ed8",backgroundColor:"#eff6ff"},fe={display:"grid",gridTemplateColumns:"repeat(auto-fill, minmax(84px, 1fr))",alignContent:"start",gap:"6px",padding:"8px",border:"1px solid #d9dee8",borderRadius:"8px",background:"#fbfdff",marginBottom:"8px",maxHeight:"126px",overflowY:"auto"},ze={...fe,gridTemplateColumns:"repeat(auto-fill, minmax(34px, 1fr))",maxHeight:"118px",overflowY:"auto"},Ve={border:"1px solid #2563eb",background:"#2563eb",color:"white",borderRadius:"7px",padding:"6px 12px",fontSize:"13px",fontWeight:700,cursor:"pointer",minHeight:"32px",outline:"none"},ge={border:"1px solid #cfd6e3",background:"#f8fafc",color:"#263244",borderRadius:"7px",padding:"5px 9px",fontSize:"12px",cursor:"pointer",minHeight:"28px",outline:"none"},Ue={...ge,minHeight:"30px",padding:"4px 7px"},G={border:"1px solid #cfd6e3",borderRadius:"6px",background:"white",color:"#263244",fontSize:"12px",height:"30px",outline:"none"},We={...G,width:"100%",minHeight:"30px",padding:"0 7px"},Ye={width:"100%",height:"215px",boxSizing:"border-box",overflowY:"auto",border:"1px solid #d9dee8",borderRadius:"8px",padding:"13px",outline:"none",background:"white",color:"#111827",fontSize:"18px",lineHeight:1.75,whiteSpace:"pre-wrap",wordBreak:"break-word",fontFamily:"ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"},Xe=Ce(Ie),he=document.getElementById("root");if(!he)throw new Error("Root element not found");const Ge=ke.createRoot(he);Ge.render(x.jsx(m.StrictMode,{children:x.jsx(Xe,{})}));
