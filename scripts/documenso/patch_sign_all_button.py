"""Patch (e) — Sign-All-My-Fields button for sam@bebang.ph.

PROBLEM
-------
Documenso v2's signing flow requires clicking each field individually on the
PDF (or using the "Next field" navigation in the widget). For Sam, who signs
many documents per week with multiple signature/name/date fields per envelope,
this is repetitive. Sam asked for a single "Sign All" button that fills every
applicable field on his behalf in one press.

CONSTRAINTS
-----------
- Gate to sam@bebang.ph only. Other signers continue to use the per-field flow
  so audit-log timing on countersigned contracts looks human.
- One FIELD_SIGNED audit-log row per field — same trail as manual clicks.
- Sustainable: no React state hacks. Pure DOM script that piggybacks on the
  existing field-click handlers (the ones that would fire if Sam clicked each
  field himself).

FIX
---
Append a self-executing function to `document-signing-page-view-v2-<hash>.js`
that, on every signing-page mount, observes the DOM for the signing widget,
checks that the current recipient's email is `sam@bebang.ph`, and injects a
"Sign All My Fields" button into the widget footer.

When clicked, the button iterates unsigned fields assigned to the current
recipient (read from `.field-card-container[data-inserted="false"]` DOM
markers) and:
  1. Dispatches a synthetic click on each
  2. If a dialog opens (NAME/EMAIL/DATE/INITIALS/NUMBER/TEXT), auto-fills
     with the value already known to the widget (full name, email, today's
     date, initials derived from name)
  3. Submits the dialog
  4. Moves to the next field

SIGNATURE and FREE_SIGNATURE fields auto-apply the saved signature without
opening a dialog (Documenso behaviour), so they're the simplest case.

USAGE
-----
    python patch_sign_all_button.py --target /path/to/document-signing-page-view-v2-<hash>.js
    python patch_sign_all_button.py --target /path/to/file --verify-only
    python patch_sign_all_button.py --search-root /app/apps/remix/build/client/assets

Same shape as the four prior patch scripts. Designed to run inside the
Dockerfile build, or against an extracted file on a developer host.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

BUNDLE_GLOB = "document-signing-page-view-v2-*.js"
PATCH_MARKER = "/* BEI patch: sign-all-button */"


PATCH_BLOCK = r"""
/* BEI patch: sign-all-button */
;(function beiSignAll(){
  var TARGET_EMAIL = "sam@bebang.ph";
  var SUPPORTED_TYPES = {
    "SIGNATURE": true, "FREE_SIGNATURE": true, "INITIALS": true,
    "NAME": true, "EMAIL": true, "DATE": true
  };

  function getRecipientEmail(){
    var input = document.getElementById("email");
    if (input && input.value) return input.value.trim().toLowerCase();
    return null;
  }

  function getFullName(){
    var input = document.getElementById("full-name");
    return input ? input.value.trim() : "";
  }

  function deriveInitials(name){
    if (!name) return "";
    return name.split(/\s+/).filter(Boolean).map(function(w){ return w[0].toUpperCase(); }).join("");
  }

  function todayFormatted(){
    var d = new Date();
    var yyyy = d.getFullYear();
    var mm = String(d.getMonth()+1).padStart(2, "0");
    var dd = String(d.getDate()).padStart(2, "0");
    return yyyy + "-" + mm + "-" + dd;
  }

  function getUnsignedFields(){
    var nodes = document.querySelectorAll('.field-card-container[data-inserted="false"]');
    var out = [];
    for (var i = 0; i < nodes.length; i++){
      var t = nodes[i].getAttribute("data-field-type");
      if (SUPPORTED_TYPES[t]) out.push(nodes[i]);
    }
    return out;
  }

  function nativeInputValueSetter(){
    var d = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value");
    return d && d.set;
  }

  function setInputValue(input, value){
    var setter = nativeInputValueSetter();
    if (setter) setter.call(input, value); else input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function findDialog(){
    return document.querySelector('[role="dialog"]:not([data-bei-handled])');
  }

  function autoFillDialog(dialog, fieldType){
    dialog.setAttribute("data-bei-handled", "true");
    var fullName = getFullName();
    var email = getRecipientEmail() || "";
    var value;
    switch (fieldType){
      case "NAME":     value = fullName; break;
      case "EMAIL":    value = email; break;
      case "INITIALS": value = deriveInitials(fullName); break;
      case "DATE":     value = todayFormatted(); break;
      default:         value = "";
    }
    var inputs = dialog.querySelectorAll('input[type="text"], input[type="email"], input:not([type])');
    if (inputs.length > 0 && value){
      setInputValue(inputs[0], value);
    }
    var submit = dialog.querySelector('button[type="submit"]');
    if (submit) {
      submit.click();
      return true;
    }
    return false;
  }

  function sleep(ms){ return new Promise(function(r){ setTimeout(r, ms); }); }

  async function signOne(fieldEl){
    var fieldType = fieldEl.getAttribute("data-field-type");
    fieldEl.click();
    await sleep(450);
    var deadline = Date.now() + 4000;
    while (Date.now() < deadline){
      var d = findDialog();
      if (d){
        autoFillDialog(d, fieldType);
        await sleep(450);
        break;
      }
      if (fieldEl.getAttribute("data-inserted") === "true") break;
      await sleep(150);
    }
  }

  async function signAll(btn){
    var originalLabel = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Signing…";
    try {
      var safety = 0;
      while (safety < 100){
        var fields = getUnsignedFields();
        if (fields.length === 0) break;
        await signOne(fields[0]);
        safety++;
      }
      var remaining = getUnsignedFields().length;
      btn.textContent = remaining === 0
        ? "✓ All fields signed"
        : "Done — " + remaining + " skipped (manual input needed)";
    } catch (err) {
      console.error("[BEI sign-all]", err);
      btn.textContent = "Error — see console";
    } finally {
      setTimeout(function(){ btn.disabled = false; btn.textContent = originalLabel; }, 3000);
    }
  }

  function findFooter(){
    return document.querySelector(".embed--DocumentWidgetFooter")
        || document.querySelector(".document-widget-footer");
  }

  function attachEmailListener(){
    var input = document.getElementById("email");
    if (!input || input.getAttribute("data-bei-hooked")) return;
    input.setAttribute("data-bei-hooked", "1");
    input.addEventListener("input", recheck);
    input.addEventListener("change", recheck);
  }

  function recheck(){ try { injectButton(); } catch(e) { console.error("[BEI sign-all]", e); } }

  function injectButton(){
    attachEmailListener();
    var footer = findFooter();
    if (!footer) return;
    var existing = footer.querySelector(".bei-sign-all-btn");
    var email = getRecipientEmail();
    var noFields = getUnsignedFields().length === 0;
    // If the user no longer qualifies OR all fields are signed → remove any existing button.
    if (email !== TARGET_EMAIL || noFields) {
      if (existing) existing.remove();
      return;
    }
    if (existing) return; // already there for the right user

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "bei-sign-all-btn";
    btn.setAttribute("data-bei-feature", "sign-all");
    btn.style.cssText = [
      "grid-column: span 2",
      "margin-top: 8px",
      "padding: 10px 16px",
      "background: #16a34a",
      "color: white",
      "border: 0",
      "border-radius: 8px",
      "font-weight: 600",
      "cursor: pointer",
      "font-size: 14px",
      "box-shadow: 0 1px 2px rgba(0,0,0,0.1)"
    ].join(";");
    btn.textContent = "⚡ Sign All My Fields (BEI)";
    btn.addEventListener("mouseenter", function(){ btn.style.background = "#15803d"; });
    btn.addEventListener("mouseleave", function(){ btn.style.background = "#16a34a"; });
    btn.addEventListener("click", function(){ signAll(btn); });
    footer.appendChild(btn);
  }

  var observer = new MutationObserver(recheck);
  function startObserving(){
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["data-inserted", "value"] });
    recheck();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startObserving);
  } else {
    startObserving();
  }
})();
/* end BEI patch: sign-all-button */
"""


def detect_state(content: str) -> str:
    if PATCH_MARKER in content:
        return "patched"
    if not content.strip():
        return "unknown"
    return "unpatched"


def apply_patch(content: str) -> str:
    # Append the patch block — the bundle is an ES module so we just add a side-effect
    # IIFE at the end. ESM tolerates trailing side-effect code outside of imports/exports.
    if not content.endswith("\n"):
        content += "\n"
    return content + PATCH_BLOCK


def resolve_target(target: str | None, search_root: str | None) -> pathlib.Path:
    if target:
        p = pathlib.Path(target)
        if not p.is_file():
            raise FileNotFoundError(f"--target file not found: {target}")
        return p
    if not search_root:
        raise ValueError("Must give either --target FILE or --search-root DIR.")
    root = pathlib.Path(search_root)
    if not root.is_dir():
        raise FileNotFoundError(f"--search-root not a directory: {search_root}")
    matches = sorted(p for p in root.glob(BUNDLE_GLOB) if not p.name.endswith(".map"))
    if not matches:
        raise FileNotFoundError(f"No {BUNDLE_GLOB} under {search_root}.")
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple matches for {BUNDLE_GLOB} under {search_root}: {[str(p) for p in matches]}. "
            "Pass --target explicitly."
        )
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--target", help="Path to the signing-page-view-v2 bundle.")
    parser.add_argument("--search-root", help="Dir to glob for the bundle.")
    parser.add_argument("--verify-only", action="store_true", help="Report state without modifying.")
    args = parser.parse_args()

    try:
        target = resolve_target(args.target, args.search_root)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    content = target.read_text(encoding="utf-8")
    state = detect_state(content)
    print(f"target: {target}")
    print(f"state:  {state}")

    if args.verify_only:
        return 0 if state == "patched" else 1

    if state == "patched":
        print("Already patched. No changes made.")
        return 0
    if state == "unknown":
        print("ERROR: bundle is empty or unrecognized.", file=sys.stderr)
        return 3

    new_content = apply_patch(content)
    target.write_text(new_content, encoding="utf-8")
    print(f"OK: appended Sign-All IIFE to {target}")
    print(f"wrote: {target} ({len(new_content)} bytes, +{len(new_content) - len(content)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
