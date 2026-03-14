/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

declare module 'plotly.js-dist-min' {
  import Plotly from 'plotly.js'
  export default Plotly
}
