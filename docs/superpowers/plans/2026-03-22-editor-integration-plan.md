# Editor Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the assistant from source-edit fill into a safe multi-editor workflow: source editor stays direct-fill, PageForms gets field-level fill, and VisualEditor gets draft-only guidance.

**Architecture:** Keep the current drawer as the single assistant surface, but branch behavior by detected editor type. Source editing continues to target `wpTextbox1`; PageForms gets a field-matching layer on top of `#pfForm`; VisualEditor stays read/generate-only in phase one and routes users back to source edit for actual fill.

**Tech Stack:** MediaWiki extension modules, ResourceLoader JS/CSS, PageForms DOM, existing LabAssistant frontend, Playwright CLI validation.

---

### Task 1: Detect editor modes cleanly

**Files:**
- Modify: `images/mediawiki-app/extensions/LabAssistant/includes/ClientConfigBuilder.php`
- Modify: `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.shell.js`
- Test: manual browser checks on `action=edit`, `Special:FormEdit`, and a VisualEditor page

- [ ] **Step 1: Add editor-mode metadata in client config**

Return flags for:
- source editor (`wpTextbox1` path)
- PageForms (`FormEdit` / `formedit`)
- VisualEditor context when detectable

- [ ] **Step 2: Load the metadata in shell bootstrap**

Use the config to decide which helper entry should be injected on the current page.

- [ ] **Step 3: Verify no regression on normal non-edit pages**

Run a browser check to confirm the standard launcher still appears on ordinary content pages.

### Task 2: Preserve and harden source-editor fill

**Files:**
- Modify: `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.js`
- Modify: `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.css`
- Test: source edit page workflow with `wpTextbox1`

- [ ] **Step 1: Keep source-editor helper branch explicit**

Refactor existing `wpTextbox1` logic so it stays isolated from future PageForms/VE logic.

- [ ] **Step 2: Keep assistant-generated answer fill and preview fill unified**

Make sure both draft preview and plain answer fill continue to work through the same fill helper.

- [ ] **Step 3: Verify no auto-save**

Confirm the page remains on `action=edit` after fill and the save action is still manual.

### Task 3: Add PageForms helper entry

**Files:**
- Modify: `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.shell.js`
- Modify: `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.css`
- Test: a real `Special:FormEdit` page from private wiki

- [ ] **Step 1: Inject a PageForms-specific helper above `#pfForm`**

Add a lightweight “知识助手填表” bar similar to the current source-edit helper.

- [ ] **Step 2: Seed a form-oriented prompt**

Open the drawer with a prompt that asks for structured field suggestions instead of page prose.

- [ ] **Step 3: Verify helper appears only on form pages**

Check it does not appear on normal content pages or source-edit pages where the source helper already exists.

### Task 4: Add PageForms field matching

**Files:**
- Modify: `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.js`
- Test: one or more real forms used by private wiki (prefer `Shot记录` and one structured entry form)

- [ ] **Step 1: Build a form field inventory**

Enumerate text inputs, textareas, and selects under `#pfForm`, collecting label text, field names, IDs, and element references.

- [ ] **Step 2: Define a conservative matching strategy**

Match assistant field suggestions to form controls by normalized label/name aliases only; do not guess aggressively.

- [ ] **Step 3: Render fill controls**

In the assistant result, show:
- fill this field
- fill all matched fields

- [ ] **Step 4: Dispatch input/change events**

When filling a field, update the control and fire the expected browser events so PageForms widgets stay in sync when possible.

- [ ] **Step 5: Verify no form submission**

Ensure field fill never triggers submit.

### Task 5: Add VisualEditor phase-one guidance

**Files:**
- Modify: `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.shell.js`
- Modify: `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.js`
- Test: page where VisualEditor is available

- [ ] **Step 1: Detect VisualEditor context conservatively**

Only add VE-specific behavior when there is a reliable signal that VE is active or the page is in VE edit mode.

- [ ] **Step 2: Provide helper entry**

Allow opening the assistant from VE pages, but do not attempt content injection.

- [ ] **Step 3: Add “switch to source edit” guidance**

When a VE user asks for page fill, provide a clear action path to source edit with the generated draft.

- [ ] **Step 4: Verify no VE DOM mutation**

Confirm the first implementation does not try to patch VE internals.

### Task 6: Validate with browser workflows

**Files:**
- Create: `backups/validation/editor-fill-pageforms-20260322.md`
- Test: Playwright-driven browser validation

- [ ] **Step 1: Validate source-editor flow**

Check helper display, drawer open, draft generation, fill confirmation, and `wpTextbox1` replacement.

- [ ] **Step 2: Validate one PageForms flow**

Check helper display, assistant field suggestion, and one-click fill into matched controls.

- [ ] **Step 3: Validate one VisualEditor flow**

Check helper display and draft/guidance path without direct content injection.

- [ ] **Step 4: Save validation notes and snapshots**

Record the exact snapshot files and key pass/fail findings in the validation note.
