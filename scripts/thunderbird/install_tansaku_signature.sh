#!/usr/bin/env bash
# Install tansaku@gmail.com HTML signature into Thunderbird (identity id2).
# Restart Thunderbird after running.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TB_PROFILE="${TB_PROFILE:-$HOME/Library/Thunderbird/Profiles/magfbx3x.default-release}"
SIG_SRC="$REPO_ROOT/assets/thunderbird/tansaku-gmail-signature.html"
SIG_DEST="$TB_PROFILE/signatures/tansaku-gmail.html"
USER_JS="$TB_PROFILE/user.js"
IDENTITY_ID="${TANSaku_IDENTITY_ID:-id2}"

if [[ ! -f "$SIG_SRC" ]]; then
  echo "Signature template not found: $SIG_SRC" >&2
  exit 1
fi

mkdir -p "$TB_PROFILE/signatures"
cp "$SIG_SRC" "$SIG_DEST"

MARKER="AR-Comedy tansaku@gmail.com signature"
if [[ -f "$USER_JS" ]] && grep -q "$MARKER" "$USER_JS"; then
  # Replace existing block between markers
  python3 - "$USER_JS" "$SIG_DEST" "$IDENTITY_ID" <<'PY'
import re
import sys
from pathlib import Path

path, sig_dest, identity_id = sys.argv[1:4]
marker = "AR-Comedy tansaku@gmail.com signature"
text = Path(path).read_text(encoding="utf-8")
block = f'''// BEGIN {marker}
user_pref("mail.identity.{identity_id}.htmlSig", true);
user_pref("mail.identity.{identity_id}.attach_signature", true);
user_pref("mail.identity.{identity_id}.sig_file", "{sig_dest}");
user_pref("mail.identity.{identity_id}.sig_bottom", true);
// END {marker}
'''
pattern = re.compile(
    rf"// BEGIN {re.escape(marker)}.*?// END {re.escape(marker)}\n?",
    re.DOTALL,
)
if pattern.search(text):
    text = pattern.sub(block, text)
else:
    text = text.rstrip() + "\n\n" + block
Path(path).write_text(text, encoding="utf-8")
PY
else
  cat >> "$USER_JS" <<EOF

// BEGIN $MARKER
user_pref("mail.identity.${IDENTITY_ID}.htmlSig", true);
user_pref("mail.identity.${IDENTITY_ID}.attach_signature", true);
user_pref("mail.identity.${IDENTITY_ID}.sig_file", "$SIG_DEST");
user_pref("mail.identity.${IDENTITY_ID}.sig_bottom", true);
// END $MARKER
EOF
fi

echo "Installed signature to: $SIG_DEST"
echo "Updated: $USER_JS"
echo "Restart Thunderbird, then compose from tansaku@gmail.com to preview."
