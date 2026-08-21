"""amd_patients_uploadfile - AMD uploadfile action. THE ONE WRITE TOOL.

SPEC Appendix C defect 5, fixed here: the copied handler was a
NotImplementedError stub. The implementation below is transcribed from
patient-intake's vendored client (AMDClient.uploadfile), which is the
reference for this action:

  - action uploadfile, class files
  - all metadata rides on an INNER <file> element, never on ppmdmsg
  - <filecontents> is a child of <file>
  - savechanges="true" is required
  - a <grouplist>/<group>/<categorylist>/<category> selects the chart
    section; MISC / Unspecified is the documented default
  - the decoded payload is hard-capped at 1024 KB, client-side, before
    the network round-trip (AMD enforces the same cap server-side)

Serving this tool takes three separate keys turning: WRITE_TOOLS_ENABLED
globally (SPEC 9.1), may_write carrying this tool name on the caller's
token (SPEC 10.3), and the tool being verified (SPEC 9.2). The worker
checks all three before the handler is reached.

PHI note: file_contents_b64 is PHI. It goes to AdvancedMD and nowhere
else. It is never logged and never named in an error.
"""
from __future__ import annotations

import base64
import binascii
from typing import Any

from lxml import etree

from ._common import get_client, raw_to_dict

ACTION = "uploadfile"
WRITE_ACTION = True
TIER = 2
PERMITTED_ACTIONS = ("uploadfile",)

#: SPEC 15: uploadfile decoded size cap, in bytes.
MAX_DECODED_BYTES = 1024 * 1024


def _build_file_element(
    *,
    patient_id: str,
    file_name: str,
    file_ext: str,
    filetype: str,
    description: str,
    file_contents_b64: str,
) -> Any:
    file_el = etree.Element(
        "file",
        name=file_name,
        description=description,
        filetype=filetype,
        fileext=file_ext,
        visitid="",
        profileid="",
        facilityid="",
        providerid="",
        dos="",
        comments="",
        patientid=patient_id,
        referringproviderid="",
        savechanges="true",
        zipmode="0",
    )
    grouplist = etree.SubElement(file_el, "grouplist")
    group = etree.SubElement(
        grouplist, "group", id="4", code="MISC", name="Miscellaneous"
    )
    categorylist = etree.SubElement(group, "categorylist")
    etree.SubElement(
        categorylist,
        "category",
        id="25",
        filegroupfid="4",
        code="MIUNSP",
        name="Unspecified",
        filetype="0",
        level="0",
        default="1",
    )
    contents_el = etree.SubElement(file_el, "filecontents")
    contents_el.text = file_contents_b64
    return file_el


def _document_ref(raw_dict: Any) -> str:
    """Pull AMD's opaque document reference out of the reply.

    Mirrors the reference client: the new file id rides on <file>, or on
    <Results>; a success with no explicit id returns the sentinel, and the
    caller's read-back is then the authority on whether the doc landed.
    """

    def _walk(node: Any) -> str:
        if not isinstance(node, dict):
            return ""
        tag = node.get("_tag")
        if tag in ("file", "Results", "results"):
            found = (node.get("_attrs") or {}).get("id", "").strip()
            if found:
                return found
        for child in node.get("_children") or []:
            found = _walk(child)
            if found:
                return found
        return ""

    return _walk(raw_dict) or "uploaded"


async def handle(
    *,
    patient_id: str,
    file_name: str,
    file_contents_b64: str,
    file_ext: str | None = None,
    filetype: str = "GENERAL",
    description: str = "",
    local_file_size_hint_kb: int | None = None,
) -> dict[str, Any]:
    if not patient_id or not file_name or not file_contents_b64:
        return {
            "error": "bad_input",
            "details": {
                "reason": "patient_id, file_name and file_contents_b64 required"
            },
        }

    # Pre-flight on the caller's hint, then the authoritative check on the
    # decoded length. Neither branch echoes the payload.
    if local_file_size_hint_kb is not None and int(local_file_size_hint_kb) > 1024:
        return {
            "error": "too_large",
            "details": {"limit_kb": 1024, "hint_kb": int(local_file_size_hint_kb)},
        }
    try:
        decoded_len = len(base64.b64decode(file_contents_b64, validate=True))
    except (binascii.Error, ValueError):
        return {
            "error": "bad_input",
            "details": {"reason": "file_contents_b64 is not valid base64"},
        }
    if decoded_len > MAX_DECODED_BYTES:
        return {
            "error": "too_large",
            "details": {"limit_kb": 1024, "decoded_kb": decoded_len // 1024},
        }

    if file_ext:
        ext = file_ext.lstrip(".")
    elif "." in file_name:
        ext = file_name.rsplit(".", 1)[1]
    else:
        ext = ""

    file_el = _build_file_element(
        patient_id=patient_id,
        file_name=file_name,
        file_ext=ext,
        filetype=filetype or "GENERAL",
        description=description or "",
        file_contents_b64=file_contents_b64,
    )

    client = get_client()
    # The metadata rides on the inner <file>, so NO attrs go on ppmdmsg.
    reply = await client.call("uploadfile", "files", children=[file_el])
    raw_dict = raw_to_dict(reply)
    return {
        "patient_id": patient_id,
        "file_name": file_name,
        "uploaded": True,
        "document_ref": _document_ref(raw_dict),
        "decoded_bytes": decoded_len,
    }
